import asyncio
import glob
import os, os.path
from pathlib import Path

import xarray as xr

from lfmc.query import ShapeQuery
from lfmc.results.Abstracts import Abstracts
from lfmc.results.Author import Author
import datetime as dt
from lfmc.models.Model import Model
from lfmc.results.ModelResult import ModelResult
from lfmc.models.ModelMetaData import ModelMetaData
from lfmc.query.SpatioTemporalQuery import SpatioTemporalQuery
from lfmc.models.dummy_results import DummyResults

import logging

logging.basicConfig(filename='/var/log/lfmcserver.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)


class YebraModel(Model):

    def __init__(self):

        self.name = "yebra"

        # TODO - Proper metadata!
        authors = [
            Author(name="Marta Yebra", email="marta.yebra@anu.edu.au", organisation="ANU")
        ]

        pub_date = dt.datetime(2015, 6, 1)

        abstract = Abstracts("")

        self.metadata = ModelMetaData(authors=authors,
                                      published_date=pub_date,
                                      fuel_types=["profile"],
                                      doi="http://dx.doi.org/10.13140/RG.2.2.36184.70403",
                                      abstract=abstract)

        self.mode = "wet"  # "wet" or "dry"
        self.ident = "Yebra"
        self.code = "LVMC"
        self.path = os.path.abspath(Model.path() + 'Yebra') + '/'
        self.output_path = os.path.abspath(self.path + "LVMC") + '/'
        self.data_path = self.output_path

        # Metadata about initialisation for use in ModelSchema
        self.parameters = {}

        self.outputs = {
            "type": "fuel moisture",
            "readings": {
                "prefix": "LVMC",
                "path": self.output_path,
                "suffix": ".nc"
            }
        }

    def all_netcdfs(self):
        """
        Pattern matches potential paths where files could be stored to those that actually exist.
        Warning: Files outside this directory aren't indexed and won't get ingested.
        :return:
        """
        possibles = [p for p in glob.glob(self.path + "australia_LVMC_*.nc")]
        return [f for f in possibles if Path(f).is_file()]
