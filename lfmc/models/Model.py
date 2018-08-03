import asyncio
import subprocess
import urllib.request
from abc import abstractmethod
from urllib.error import URLError
import shutil
import os
from marshmallow import Schema, fields
from pathlib2 import Path

from lfmc.models.ModelMetaData import ModelMetaDataSchema
from lfmc.results.DataPoint import DataPoint
from lfmc.models.rx.ObservableModel import ObservableModel

import zlib


import logging
import random

logging.basicConfig(filename='/var/log/lfmcserver.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)


class Model(ObservableModel):
    def __init__(self):
        self.name = "Base Model Class"
        self.metadata = {}
        self.parameters = {}
        self.outputs = {}
        self.tolerance = 0
        self.ident = ""
        self.code = ""
        pass

    def __init__(self, model):
        """ Copy-constructor """
        self.name = model.name
        self.metadata = model.metadata
        self.parameters = model.parameters
        self.outputs = model.outputs
        self.tolerance = model.tolerance
        self.ident = model.ident
        self.code = model.code

        pass

    @staticmethod
    def path():
        return '/FuelModels/'


    def date_is_cached(self, when):

        # TODO -Swift Object Storage Checking

        file_path = Path(self.outputs["readings"]['path'])
        if not file_path.is_dir():
            os.makedirs(file_path)

        ok = Path(self.netcdf_name_for_date(when)).is_file()
        logger.debug("\n--> Checking for existence of NetCDF @ %s for %s: %s" %
                     (file_path, when.strftime("%d %m %Y"), ok))

        # TODO -if OK put the file into Swift Storage

        return ok

    @staticmethod
    async def do_download(url, resource, path):
        uri = url + resource
        logger.debug("\n> Downloading...\n--> Retrieving: {} \n--> Saving to: {}\n".format(uri, path))

        try:
            # await asyncio.sleep(random.random() * 5.)
            # urllib.request.urlretrieve(uri, path)
            #with urllib.request.urlopen(uri) as response, open(path, 'wb') as out_file:
            #    shutil.copyfileobj(response, out_file)
            # complete = subprocess.Popen(['curl', uri, '-o', path, '--create-dirs'])
            # loop = asyncio.get_event_loop()
            # task = asyncio.create_subprocess_exec('curl %s -o %s --create-dirs' % (uri, path), loop=loop)
            #
            # future = asyncio.run_coroutine_threadsafe(task, loop)
            # result = future.result(30)  # Wait for the result with a timeout

            p = subprocess.run(['curl', url, '-f', '-o', path], shell=False, check=True)

        except URLError as e:
            msg = '500 - An unspecified error has occurred.\n'
            if hasattr(e, 'reason'):
                msg += 'We failed to reach a server.\n'
                msg += 'Reason: %s\n' % e.reason
            if hasattr(e, 'code'):
                msg += 'The server could not fulfill the request.\n'
                msg += 'Error code: %s\n' % e.code
            raise URLError(msg)

        logger.debug('\n----> Download complete.\n')
        return path

    @staticmethod
    async def do_expansion(archive_file):
        logger.info("\n--> Expanding: %s" % archive_file)
        try:
            if str(archive_file).endswith('.Z'):
                subprocess.run(['uncompress', '-k', archive_file], shell=False, check=True)
                # await asyncio.create_subprocess_shell('uncompress -k %s' % archive_file)
            else:
                logger.warning('Not a .Z file!')

        except FileNotFoundError as e:
            logger.warning("\n--> Expanding: %s, failed.\n%s" % (archive_file, e))
            return False
        except OSError as e:
            logger.info("\n--> Removing: %s, was not necessary.\n %s" % (archive_file, e))
        return True

    @staticmethod
    async def get_datapoint_for_param(b, param):
        """
        Takes the mean min and max values for datapoints at a particular time slice.
        :param b:
        :param param:
        :return:
        """

        bin_ = b.to_dataframe()

        # TODO - This is a quick hack to massage the datetime format into a markup suitable for D3 & ngx-charts!
        tvalue = str(b["time"].values).replace('.000000000', '.000Z')
        avalue = bin_[param].median()

        logger.debug(
            "\n>>>> Datapoint creation. (time={}, value={})".format(tvalue, avalue))

        asyncio.sleep(1)

        return DataPoint(observation_time=tvalue,
                         value=avalue,
                         mean=bin_[param].mean(),
                         minimum=bin_[param].min(),
                         maximum=bin_[param].max(),
                         deviation=bin_[param].std())

    pass


class ModelSchema(Schema):
    name = fields.String()
    metadata = fields.Nested(ModelMetaDataSchema, many=False)
    parameters = fields.String()
    outputs = fields.String()
    ident = fields.String()
    code = fields.String()
