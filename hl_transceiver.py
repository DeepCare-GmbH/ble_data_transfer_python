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
from ble_data_transfer_python.ll_receiver import LLReceiver
from ble_data_transfer_python.ll_sender import LLSender

from ble_data_transfer_python.hl_download import HLDownload
from ble_data_transfer_python.hl_upload import HLUpload


class HLTransceiver():
    """Class providing sending and receiving of data.
    """

    def __init__(self, ll_receiver: LLReceiver, ll_sender: LLSender, root_path: str, cb_download_finished: Callable[[pathlib.Path], None]) -> None:
        """Constructor.

        Args:
            ll_receiver (LLReceiver): Low level file transfer instance handling the receiving chunk download
            ll_sender (LLSender): Low level file transfer instance handling the sending chunk upload
            root_path (str): root folder for upload and download folder used for file transfer
            cb_download_finished (Callable[[pathlib.Path], None]): user callback executed if a file was downloaded completely
        """

        self._logger = logging.getLogger(self.__class__.__name__)
        coloredlogs.install(logger=self._logger)

        # current request
        self._request = StartTransferRequest()
        # current response
        self._response = StartTransferResponse()

        self._last_direction: StartTransferRequestDirection = None

        # create downloader instance
        self._download = HLDownload(
            root_path, ll_receiver, cb_download_finished)
        # set callback to consume downloaded chunks
        ll_receiver.cb_new_data = self._download.add_chunk

        # create uploader instance
        self._upload = HLUpload(root_path, ll_sender, 1024 * 100)

        self._logger.info('high level transceiver ready')

    def set_request(self, request: StartTransferRequest) -> None:

        self._logger.info(request)

        self._last_direction = request.direction
        if self._last_direction == StartTransferRequestDirection.PHONE_TO_DEVICE:
            self._download.set_request(request)
        else:
            self._upload.set_request(request)

    def get_response(self) -> StartTransferResponse:

        if self._last_direction == StartTransferRequestDirection.PHONE_TO_DEVICE:
            response = self._download.get_response()
        else:
            response = self._upload.get_response()

        self._logger.info(response)

        return response