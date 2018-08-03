import hug
import asyncio

from marshmallow import fields, pprint
from rx import Observer

from lfmc.models.Model import ModelSchema
from lfmc.process.Conversion import Conversion
from lfmc.query.ShapeQuery import ShapeQuery
from lfmc.results import ModelResult
from lfmc.results.ModelResult import ModelResultSchema
from lfmc.models.ModelRegister import ModelRegister, ModelsRegisterSchema
from lfmc.monitor.RequestMonitor import RequestMonitor

import numpy as np
import pandas as pd
import xarray as xr
import geojson

import sys
import io
import traceback
import logging
import lfmc.config.debug as dev

logging.basicConfig(filename='/var/log/lfmcserver.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)

api_ = hug.API(__name__)
api_.http.add_middleware(hug.middleware.CORSMiddleware(api_, max_age=10))

api = hug.get(on_invalid=hug.redirect.not_found)

suffix_output = hug.output_format.suffix({'.json': hug.output_format.pretty_json,
                                          '.mp4': hug.output_format.mp4_video,
                                          '.mov': hug.output_format.mov_video,
                                          '.nc': hug.output_format.file})

content_output = hug.output_format.on_content_type(
    {'application/x-netcdf4': hug.output_format.file})


@hug.cli()
@api.urls('/validate', versions=range(1, 2))
def validate():
    mr = ModelRegister()
    return mr.validate_catalog()


@hug.cli()
@hug.post(('/fuel', '/fuel.json', '/fuel.mp4', '/fuel.mov', '/fuel.nc'), versions=1, output=suffix_output)
async def fuel(geo_json,
               start: fields.String(),
               finish: fields.String(),
               weighted: fields.Bool(),
               models: hug.types.delimited_list(','),
               response_as: hug.types.number):
    """
    :param geo_json:
    :param start:
    :param finish:
    :param weighted:
    :param models:
    :param response_as:
    :return:
    """
    query = ShapeQuery(start=start, finish=finish,
                       geo_json=geo_json, weighted=weighted)

    rm = RequestMonitor()
    rm.log_request(query)

    logger.info(query.temporal.start.strftime("%Y%m%d"))
    logger.info(query.temporal.finish.strftime("%Y%m%d"))

    # Which models are we working with?
    model_subset = ['DFMC']
    if models is not None:
        model_subset = models

    mr = ModelRegister()
    # logger.debug("Answering fuel geojson shaped time-series now...")

    # Default case
    response = None
    errors = None
    # Switch schema on response_as
    # 0. Timeseries JSON
    # 1. MP4
    # 2. NetCDF
    if response_as == 0:
        logger.info("Responding to JSON query")
        schema = ModelResultSchema(many=True)
        response, errors = schema.dump(
            await asyncio.gather(*[mr.get(model).get_shaped_timeseries(query) for model in model_subset]))

    elif response_as == 1:
        logger.info("Responding to JSON query")
        schema = ModelResultSchema(many=True)
        response, errors = schema.dump(
            await asyncio.gather(*[mr.get(model).get_shaped_timeseries(query) for model in model_subset]))
        logger.info("Responding to MP4 query...")
        # TODO - only returns first model at the moment
        mpg = (await asyncio.gather(*[mr.get("dead_fuel").mpg(query)]))[0]
        # response = await mr.get("dead_fuel").mpg(query)
        response.movie_file = 'http://128.250.160.167:8002/v1/'

    elif response_as == 2:
        logger.info("Responding to NETCDF query...")
        # TODO - only returns first model at the moment
        response = (await asyncio.gather(*[mr.get(model).get_netcdf(query) for model in model_subset]))[0]
        errors = []

    asyncio.sleep(1)

    if dev.DEBUG:
        logger.debug(response)

    if len(errors) > 0:
        logger.exception(errors)
        return errors
    else:
        # Default Response
        query.logResponse()
        return response


@hug.exception(Exception)
def handle_exception(exception):
    logger.exception(exception)

    exc_type, exc_value, exc_traceback = sys.exc_info()
    output = io.StringIO()

    traceback.print_exception(exc_type, exc_value, exc_traceback,
                              limit=2, file=output)

    message = {'code': 500, 'error': '{}'.format(output.getvalue())}
    output.close()
    return message


# @hug.cli()
# @hug.post(('/fuel', '/fuel.json', '/fuel.mp4', '/fuel.mov', '/fuel.nc'), versions=2, output=suffix_output)
# async def fuel_moisture(geo_json,
#                         start: fields.String(),
#                         finish: fields.String(),
#                         weighted: fields.Bool(),
#                         models: hug.types.delimited_list(','),
#                         response_as: hug.types.number):
#     """
#         :param geo_json:
#         :param start:
#         :param finish:
#         :param weighted:
#         :param models:
#         :param response_as:
#         :return:
#         """
#     query = ShapeQuery(start=start, finish=finish,
#                        geo_json=geo_json, weighted=weighted)
#
#     mr = ModelRegister()
#     omr = ObservedModelResponder()
#     rm = RequestMonitor()
#     rm.log_request(query)
#     logger.info(query)
#
#     # Which models are we working with?
#     model_subset = ['DFMC']
#     if models is not None:
#         model_subset = models
#
#     mr.apply_shape_for_timeseries(query)
#     mr.subscribe(omr)
#
#     return omr.get()


@hug.cli()
@api.urls('/monitors', versions=range(1, 2))
async def monitors():
    return {"monitors": ["processes", "requests"]}


@hug.cli()
@api.urls('/monitors/requests/complete', versions=range(1, 2))
async def monitor_complete_requests():
    rm = RequestMonitor()
    return rm.completed_requests()


@hug.cli()
@api.urls('/monitors/requests/all', versions=range(1, 2))
async def monitor_all_requests():
    return RequestMonitor().all_requests()


@hug.cli()
@api.urls('/monitors/requests/active', versions=range(1, 2))
async def monitor_active_requests():
    return RequestMonitor().open_requests()


@hug.cli()
@api.urls('/monitors/processes', versions=range(1, 2))
async def monitor_processes():
    return pprint({"processes": asyncio.Task.all_tasks()})


@hug.cli()
@api.urls('/log', versions=range(1, 2))
async def get_log():
    # log = read_server_log_file()
    # return log
    return "No logging yet..."


@hug.cli()
@api.urls('/models', versions=range(1, 2))
async def get_models():
    if dev.DEBUG:
        logger.debug('Got models call. Answering now...')
    model_register = ModelRegister()
    models_list_schema = ModelsRegisterSchema()
    resp, errors = models_list_schema.dump(model_register)
    return resp


@hug.cli()
@api.urls('/model', examples='?name=ffdi', versions=range(1, 2), content_output=hug.output_format.pretty_json)
async def get_model(name):
    model_register = ModelRegister()
    model_schema = ModelSchema()
    resp, errors = model_schema.dump(model_register.get(name))
    return resp


@hug.post('/convert.json', versions=range(1, 2), content_output=hug.output_format.file)
async def get_converted_shapefile(shp: str):
    logger.debug('Got conversion request: ' + shp)
    resp = Conversion.convert_this(shp)
    #
    # try:
    #     del resp['crs']
    # except KeyError:
    #     # pass
    #     logger.debug(resp)
    return resp


class ObservedModelResponder(Observer):
    """ Used for internal testing. Simply Observes and prints to the console."""

    def on_next(self, r: ModelResult):
        logger.debug('## ObservedModelResponder ##')
        logger.debug('## ---------------------- ##')

        mrs = ModelResultSchema()
        logger.debug(mrs.dumps(r))
        self.result = mrs.dumps(r)
        pass

    def on_error(self, e):
        logger.error(e)
        self.result = e
        pass

    def on_completed(self):
        logger.info('Complete')
        # self.result = {"query": "Complete"}
        pass

    def get(self):
        resp, errors = self.result
        return resp

    def __init__(self):
        self.result = ""
        pass


if __name__ == '__main__':
    get_log.interface.cli()
    fuel.interface.cli()
    get_models.interface.cli()
    monitors.interface.cli()
    monitor_processes.interface.cli()
    monitor_all_requests.interface.cli()
    monitor_active_requests.interface.cli()
    monitor_complete_requests.interface.cli()
