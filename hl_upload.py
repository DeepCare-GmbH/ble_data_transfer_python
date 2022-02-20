#!/usr/bin/env python3

# Class providing high level data reception
# Michael Katzenberger
# 30.12.2021

import logging
import pathlib
from typing import Callable, List

import coloredlogs

from ble_data_transfer_python.gen.deepcare.messages import (
    StartTransferRequest, StartTransferRequestDirection, StartTransferResponse)
from ble_data_transfer_python.ll_sender import LLSender


class HLUpload:
    def __init__(self, root_path: str) -> None:

        self._logger = logging.getLogger(self.__class__.__name__)
        coloredlogs.install(logger=self._logger)

        self._upload_path = pathlib.Path(root_path).joinpath('upload')
        self._upload_path.mkdir(parents=True, exist_ok=True)

        # current request
        self._request = StartTransferRequest()
        # current response
        self._response = StartTransferResponse()
