import asyncio
import os
import os.path
import glob
from pathlib import Path

import pandas as pd
from lfmc.models.BomBasedModel import BomBasedModel
from lfmc.results.Abstracts import Abstracts
from lfmc.results.Author import Author
import datetime as dt
from lfmc.models.Model import Model
from lfmc.models.ModelMetaData import ModelMetaData
import logging

logging.basicConfig(filename='/var/log/lfmcserver.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)

FFDI_PRODUCT = 'IDV71117_VIC_FFDI_SFC.nc'


class FFDIModel(BomBasedModel):

    def __init__(self):
        self.name = "ffdi"

        # TODO - Proper metadata!
        authors = [
            Author(name="", email="",
                   organisation="")
        ]
        pub_date = dt.datetime(2015, 9, 9)
        abstract = Abstracts("")
        self.metadata = ModelMetaData(authors=authors, published_date=pub_date, fuel_types=["surface"],
                                      doi="http://dx.doi.org/10.1016/j.rse.2015.12.010", abstract=abstract)

        self.path = os.path.abspath(Model.path() + 'FFDI') + '/'
        self.ident = "Forest Fire Danger"
        self.code = "FFDI"
        self.crs = "EPSG:3111"
        self.outputs = {
            "type": "index",
            "readings": {
                "path": self.path,
                "url": "",
                "prefix": "FFDI_SFC",
                "suffix": ".nc"
            }
        }

    def netcdf_name_for_date(self, when):
        return self.netcdf_names_for_date(when, FFDI_PRODUCT)



