import asyncio
import glob

import gdal
import pandas as pd
import os, os.path
import numpy as np
import pyproj
import requests
import xarray as xr
import datetime as dt

from pathlib2 import Path
import lfmc.config.debug as dev
from lfmc.models.Model import Model
from lfmc.models.ModelMetaData import ModelMetaData
from lfmc.models.dummy_results import DummyResults
from lfmc.query import ShapeQuery
from lfmc.query.SpatioTemporalQuery import SpatioTemporalQuery
from lfmc.resource.SwiftStorage import SwiftStorage
from lfmc.results.Abstracts import Abstracts
from lfmc.results.Author import Author
from lfmc.results.DataPoint import DataPoint
from lfmc.results.ModelResult import ModelResult

import logging

logging.basicConfig(filename='/var/log/lfmcserver.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)


class LiveFuelModel(Model):

    def __init__(self):
        self.name = "live_fuel"

        # TODO - Proper metadata!
        authors = [
            Author(name="Test1", email="test1@example.com", organisation="Test Organisation"),
            Author(name="Test2", email="test2@example.com", organisation="Test Organisation"),
            Author(name="Test3", email="test3@example.com", organisation="Test Organisation")
        ]
        pub_date = dt.datetime(2015, 9, 9)

        # Which products from NASA
        product = "MOD09A1"
        version = "6"

        # AIO bounding box lower left longitude, lower left latitude, upper right longitude, upper right latitude.
        bbox = "108.0000,-45.0000,155.0000,-10.0000"

        self.modis_meta = product, version, bbox

        abstract = Abstracts("NYA")

        self.metadata = ModelMetaData(authors=authors,
                                      published_date=pub_date,
                                      fuel_types=["surface"],
                                      doi="http://dx.doi.org/10.1016/j.rse.2015.12.010",
                                      abstract=abstract)

        self.path = os.path.abspath(Model.path() + 'Live_FM') + '/'
        self.ident = "Live Fuels"
        self.code = "LFMC"
        self.parameters = {
            "surface relectance band": {
                "var": "SRB",
                "path": "",
                "url": "",
                "prefix": "SRB",
                "suffix": ".hdf",
                "dataset": ".hdf",
                "compression_suffix": ".gz"
            }
        }
        self.outputs = {
            "type": "fuel moisture",
            "readings": {
                "path": "LiveFM",
                "url": "LiveFM",
                "prefix": "LFMC",
                "suffix": "_lfmc.nc",
            }
        }

        self.storage_engine = SwiftStorage()
        # {"parameters": self.parameters, "outputs": self.outputs})

    # @deprecated
    # def check_for_netrc(self):
    #     cmdline("cat /home/arawlins/.netrc")
    #

    def netcdf_name_for_date(self, when):
        return "{}{}_{}{}".format(self.outputs["readings"]["path"],
                                  self.outputs["readings"]["prefix"],
                                  when.strftime("%Y%m%d"),
                                  self.outputs["readings"]["suffix"])

    def all_netcdfs(self):
        """
        Pattern matches potential paths where files could be stored to those that actually exist.
        Warning: Files outside this directory aren't indexed and won't get ingested.
        :return:
        """
        possibles = [p for p in glob.glob("{}{}_*{}".format(self.outputs["readings"]["path"],
                                                             self.outputs["readings"]["prefix"],
                                                             self.outputs["readings"]["suffix"]))]
        return [f for f in possibles if Path(f).is_file()]

    @staticmethod
    def used_granules():
        """ Generates a list of tuples describing HV coords for granules that are used
        to generate a MODIS composite covering Australia.
        """
        return [(h, v) for h in range(27, 31) for v in range(9, 13)]

    def is_acceptable_granule(self, granule):
        return self.hv_for_modis_granule(granule) in LiveFuelModel.used_granules()

    @staticmethod
    def hv_for_modis_granule(granule):
        """ Extracts HV grid coords from naming conventions of HDF-EOS file.
        Assumes input is a file name string conforming to EOS naming conventions."""
        parts = granule.split('.')
        hv_component = parts[-4].split('v')
        h = int(hv_component[0].replace('h', ''))
        v = int(hv_component[1])
        return h, v

    def date_for_modis_granule(self, granule):
        """ Extracts the observation date from the naming conventions of a HDF-EOS file"""
        # unravel naming conventions
        parts = granule.split('.')

        # set the key for subgrouping to be the date of observation by parsing the Julian Date
        return dt.datetime.strptime((parts[1].replace('A', '')), '%Y%j')

    def get_hv(self, url):
        """ Parses a HDF_EOS URI to extract HV coords """
        uri_parts = url.split('/')
        return self.hv_for_modis_granule(uri_parts[-1])

    async def retrieve_earth_observation_data(self, url):
        """ Please note: Requires a valid .netrc file in users home directory! """
        os.chdir(self.path)
        logger.debug(url)
        file_name = url.split('/')[-1]
        logger.debug(file_name)

        xml_name = file_name + '.xml'
        hdf5_name = file_name + '_lfmc.nc'

        hdf_file = Path(file_name)
        xml_file = Path(xml_name)
        hdf5_name = Path(hdf5_name)

        if not self.storage_engine.swift_check_lfmc(hdf5_name):
            # No LFMC Product for this granule
            if not self.storage_engine.swift_check_modis(file_name):
                # No Granule held in cloud
                if (not hdf_file.is_file()) or (os.path.getsize(hdf_file) == 0):
                    # No local file either!
                    logger.debug("[Downloading]" + file_name)
                    # cmdline("curl -n -L -c cookiefile -b cookiefile %s --output %s" % (url, file_name))
                    os.system(
                        "wget -L --accept hdf --reject html --load-cookies=cookiefile --save-cookies=cookiefile %s -O %s" % (
                            url, file_name))
                    asyncio.sleep(1)

                if hdf_file.is_file():
                    # Local file now exists
                    # TODO -> Process the file and calc the Live FM here!
                    xlfmc = self.convert_modis_granule_file_to_lfmc(hdf_file)
                    # Upload the LFMC HDF5 file to swift API as well.
                    self.storage_engine.swift_put_lfmc()
                    # else:
                    #     raise CalculationError('Processing LFMC for Granule: %s failed!' % (hdf_file))

                    # Make sure to save the original source
                    if self.storage_engine.swift_put_modis(file_name):
                        os.remove(file_name)
            else:
                # MODIS Source exists but derived LFMC HDF5 does not!
                self.storage_engine.swift_get_modis(file_name)

                # TODO -> Process the file and calc the Live FM here!\
                with self.convert_modis_granule_file_to_lfmc(hdf_file) as xlfmc:
                    # Upload the LFMC HDF5 file to swift API as well.
                    self.storage_engine.swift_put_lfmc(xlfmc)

                # else:
                #     raise CalculationError('Processing LFMC for Granule: %s failed!' % (hdf_file))

            logger.debug("[OK] %s" % (file_name))

            if not self.storage_engine.swift_check_modis(xml_name):
                if (not xml_file.is_file()) or (os.path.getsize(xml_file) == 0):
                    logger.debug("[Downloading] " + xml_name)
                    os.system(
                        "wget -L --accept xml --reject html --load-cookies=cookiefile --save-cookies=cookiefile %s -O %s" % (
                            url, xml_name))
                    # cmdline("curl -n -L -c cookiefile -b cookiefile %s --output %s" % (url+'.xml', xml_name))
                if xml_file.is_file():
                    if self.storage_engine.swift_put_modis(xml_name):
                        os.remove(xml_name)
            logger.debug("[OK] %s" % (xml_name))

        else:
            # LFMC exists for this granule in Nectar Cloud already!
            logger.debug('LFMC exists for this granule in Nectar Cloud already!')

        asyncio.sleep(1)
        return hdf_file

    def group_queue_by_date(self, queue):
        grouped = {}

        logger.debug('#### Deconstructing: %s', [e for e in queue])

        # Sort the queue and group by date/granule HV coords
        for elem in queue:
            if type(elem) is list:
                logger.warning('#### Expected list of strings, got list of lists')
                for e in elem:
                    fname = e.split('/')[-1]
                    if fname.endswith('.hdf') or fname.endswith('.HDF'):
                        key = self.date_for_modis_granule(fname).strftime('%Y-%m-%d')
                        grouped.setdefault(key, []).append(e)
            else:
                fname = elem.split('/')[-1]
                if fname.endswith('.hdf') or fname.endswith('.HDF'):
                    key = self.date_for_modis_granule(fname).strftime('%Y-%m-%d')
                    grouped.setdefault(key, []).append(elem)

        return grouped
        # return queue

    def convert_modis_granule_file_to_lfmc(self, fobj):
        """
        This method combines the bands to form the LFMC values IN THE GRANULE and adds the data to existing bands,
        along with appropriate metadata

        :param fobj:
        :return: An Xarray Dataset (in-memory)
        """
        b1 = self.read_hdfeos_df_as_xarray(fobj, 'sur_refl_b01')
        b3 = self.read_hdfeos_df_as_xarray(fobj, 'sur_refl_b03')
        b4 = self.read_hdfeos_df_as_xarray(fobj, 'sur_refl_b04')
        vari = ((b4 - b1) / (b4 + b1 - b3)).clip(-1, 1)

        # Calc spectral index
        vari_max = vari.max()
        vari_min = vari.min()
        vari_range = vari_max - vari_min
        rvari = (vari - vari_min / vari_range).clip(0, 1)  # SI
        data = np.reshape(np.array(52.51 ** (1.36 * rvari)), (2400, 2400)).astype(np.float64)

        print(data.shape)
        print(pd.DataFrame(data).head())
        print(b1.coords)
        print(b1.dims)

        # captured = b1.attrs['time']  #TODO <-- DEBUG THIS ATTRIBUTE is it correct?

        captured = self.date_for_modis_granule(str(fobj))

        xrd = xr.Dataset({'LFMC': (['time', 'latitude', 'longitude'], np.expand_dims(data, axis=0))},
                         coords={'longitude': b1['longitude'],
                                 'latitude': b1['latitude'],
                                 'time': pd.date_range(captured, periods=1)})

        print(xrd)

        xrd.attrs['var_name'] = self.outputs["readings"]["prefix"]
        xrd.attrs['created'] = "%s" % (dt.datetime.now().strftime("%d-%m-%Y"))
        xrd.attrs['crs'] = '+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs '
        xrd['time:units'] = 'days since %s' % (captured.strftime("%Y-%m-%d"))
        xrd.load()

        #         lfmc_name = str(fobj) + '_lfmc.nc'
        #         xrd.to_netcdf(lfmc_name, format='NETCDF4', unlimited_dims=['time'])
        #         xrd.to_netcdf(lfmc_name)

        return xrd

    def read_hdfeos_df_as_xarray(self, file_name, data_field_name):

        grid_name = 'MOD_Grid_500m_Surface_Reflectance'
        gname = 'HDF4_EOS:EOS_GRID:"{0}":{1}:{2}'.format(file_name,
                                                         grid_name,
                                                         data_field_name)
        gdset = gdal.Open(gname)
        data = gdset.ReadAsArray().astype(np.float64)

        # Construct the grid.
        x0, xinc, _, y0, _, yinc = gdset.GetGeoTransform()
        nx, ny = (gdset.RasterXSize, gdset.RasterYSize)
        x = np.linspace(x0, x0 + xinc * nx, nx)
        y = np.linspace(y0, y0 + yinc * ny, ny)
        xv, yv = np.meshgrid(x, y)

        # In basemap, the sinusoidal projection is global, so we won't use it.
        # Instead we'll convert the grid back to lat/lons.
        sinu = pyproj.Proj("+proj=sinu +R=6371007.181 +nadgrids=@null +wktext")
        wgs84 = pyproj.Proj("+init=EPSG:4326")
        lon, lat = pyproj.transform(sinu, wgs84, xv, yv)

        # There's a wraparound issue for the longitude, as part of the tile extends
        # over the international dateline, and pyproj wraps longitude values west
        # of 180W (< -180) into positive territory.  Basemap's pcolormesh method
        # doesn't like that.
        #         lon[lon > 0] -= 360

        # Read the attributes.
        meta = gdset.GetMetadata()
        long_name = meta['long_name']
        units = meta['units']
        _FillValue = np.float64(meta['_FillValue'])
        scale_factor = np.float64(meta['scale_factor'])
        valid_range = [np.float64(x) for x in meta['valid_range'].split(', ')]

        # del gdset

        invalid = np.logical_or(data > valid_range[1],
                                data < valid_range[0])
        invalid = np.logical_or(invalid, data == _FillValue)
        data[invalid] = np.nan
        data = data / scale_factor

        # TODO - Reinstate data masking!
        data = np.ma.masked_array(data, np.isnan(data))

        df = pd.DataFrame(data, index=lat, columns=lon)
        xrd = xr.DataArray(df)
        xrd.name = data_field_name
        xrd = xrd.rename({'dim_0': 'latitude'})
        xrd = xrd.rename({'dim_1': 'longitude'})
        return xrd

    # ShapeQuery
    async def get_shaped_resultcube(self, shape_query: ShapeQuery) -> xr.DataArray:
        sr = None
        fs = await asyncio.gather(*[self.dataset_files(when) for when in shape_query.temporal.dates()])

        logger.debug('Files to open are...')
        logger.debug([str(f) for f in fs])

        fs = [f for f in fs if Path(f).is_file()]
        asyncio.sleep(1)
        if len(fs) > 0:
            with xr.open_mfdataset(fs) as ds:
                if "observations" in ds.dims:
                    sr = ds.squeeze("observations")
            sr = sr.sel(time=slice(shape_query.temporal.start.strftime("%Y-%m-%d"),
                                   shape_query.temporal.finish.strftime("%Y-%m-%d")))

            return shape_query.apply_mask_to(sr)
        else:
            return xr.DataArray([])

    async def get_shaped_timeseries(self, query: ShapeQuery) -> ModelResult:
        if dev.DEBUG:
            logger.debug(
                "\n--->>> Shape Query Called successfully on %s Model!! <<<---" % self.name)
            logger.debug("Spatial Component is: \n%s" % str(query.spatial))
            logger.debug("Temporal Component is: \n%s" % str(query.temporal))
            logger.debug("\nDerived LAT1: %s\nDerived LON1: %s\nDerived LAT2: %s\nDerived LON2: %s" %
                         query.spatial.expanded(0.05))
        dps = []
        try:
            sr = await (self.get_shaped_resultcube(query))
            sr.load()
            if dev.DEBUG:
                logger.debug("Shaped ResultCube is: \n%s" % sr)

            for r in sr['time']:
                t = r['time'].values
                o = sr.sel(time=t)
                p = self.outputs['readings']['prefix']
                df = o[p].to_dataframe()
                df = df[p]
                # TODO - This is a quick hack to massage the datetime format into a markup suitable for D3 & ngx-charts!
                m = df.median()
                dps.append(DataPoint(observation_time=str(t).replace('.000000000', '.000Z'),
                                     value=m,
                                     mean=m,
                                     minimum=df.min(),
                                     maximum=df.max(),
                                     deviation=0))
        except FileNotFoundError:
            logger.exception('Files not found for date range.')

        asyncio.sleep(1)

        return ModelResult(model_name=self.name, data_points=dps)

    async def dataset_files(self, when):
        if self.date_is_cached(when):
            return self.netcdf_name_for_date(when)  # TODO - Overload this and use 8 Day product indexing
        else:
            ds_files = await asyncio.gather(*[self.collect_granules(when)])
            asyncio.sleep(1)
            return ds_files

    def unique_from_nestedlist(self, inventory):
        unique_data = []
        if type(inventory) is list:
            for i in inventory:
                if type(i) is list:
                    unique_row = self.unique_from_nestedlist(i)
                    [unique_data.insert(0, a) for a in unique_row if a not in unique_data]
                else:
                    unique_data.insert(0, i)
        return sorted(unique_data)

    async def collect_granules(self, when):
        r = self.build_inventory_request_url(when)

        logger.debug('### Request URL for Inventory: \n', r)
        inventory = await asyncio.gather(*[self.get_inventory_for_request(r)])
        logger.debug('### Inventory to retrieve: \n', inventory)
        collected = []

        os.chdir(self.path)  # ????????

        if len(inventory) > 0:
            # Check the indexed files and don't replicate work!
            # Also check the current download queue to see if the granule is currently being downloaded.
            # split the queue by task status
            # grouped_by_date = self.group_queue_by_date(inventory)
            # for urls in list(grouped_by_date.values()):

            inventory = self.unique_from_nestedlist(inventory)
            logger.debug([i for i in inventory])
            for url in inventory:
                logger.info('Attempting download of: ', url)
                rok = await self.retrieve_earth_observation_data(url)
                asyncio.sleep(1)
                collected.append(rok)

            logger.debug([c for c in collected])
            return collected
        else:
            logger.warning('Collecting nothing!')
            return []

    async def get_inventory_for_request(self, url_string):
        r = requests.get(url_string)
        queue = []
        if r.status_code == 200:
            granules = r.text.split('\n')
            for line in granules:
                if len(line) > 0 and self.is_acceptable_granule(line):
                    queue.append(line)
        else:
            raise ("[Error] Can't continue. Didn't receive what we expected from USGS / NASA.")
        return queue

    def build_inventory_request_url(self, when):
        """
        Uses USGS LPDAAC inventory service to select files.
        Gathers entirety of Australia rather than using query BBOX.
        """
        product, version, bbox = self.modis_meta

        rurl = "https://lpdaacsvc.cr.usgs.gov/services/inventory?product=" + product + "&version=" + \
               version + "&bbox=" + bbox + "&date=" + when.strftime('%Y-%m-%d') + "&output=text"

        return rurl
