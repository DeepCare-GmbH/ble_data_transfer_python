#!/usr/bin/env python3

# Class providing high level data reception
# Michael Katzenberger
# 30.12.2021

import hashlib
import logging
import pathlib
from math import ceil
from typing import List

import coloredlogs

from ble_data_transfer_python.gen.deepcare.messages import (
    StartTransferRequest, StartTransferResponse, StartTransferResponseStatus)
from ble_data_transfer_python.gen.deepcare.transfer_data import TransferData
from ble_data_transfer_python.ll_sender import LLSender


class HLUpload:

    def __init__(self, root_path: str, ll_sender: LLSender, chunk_size=1024) -> None:

        self._logger = logging.getLogger(self.__class__.__name__)
        coloredlogs.install(logger=self._logger)

        # take over low lever sender
        self._ll_sender = ll_sender
        self._chunk_size = chunk_size

        self._upload_path = pathlib.Path(root_path).joinpath('upload')
        self._upload_path.mkdir(parents=True, exist_ok=True)

        # current request
        self._request = StartTransferRequest()
        # current response
        self._response = StartTransferResponse()

        self._chunk_generator: bytes = None

    def _reset(self, request: StartTransferRequest):

        # create response for initial data transfer
        self._response = StartTransferResponse()

        # copy filename
        self._response.filename = request.filename

        # check if requested file is available
        upload_file = self._upload_path.joinpath(request.filename)
        if not upload_file.exists():
            self._response.status = StartTransferResponseStatus.FILE_NOT_FOUND
            return

        # number of chunks
        self._response.chunks = ceil(
            upload_file.stat().st_size / self._chunk_size)

        # transfer is now active
        self._response.status = StartTransferResponseStatus.TRANSFER

        # create generator
        self._chunk_generator = self._split(upload_file)

    def _split(self, file_name: pathlib.Path) -> bytes:

        with open(file_name, 'rb') as f_in:
            data = bytes(1)
            while len(data) > 0:
                data = f_in.read(self._chunk_size)
                yield data

    def set_request(self, request: StartTransferRequest) -> None:

        # empty hash starts a new request
        if not request.hash:

            # start new transfer with requested file
            self._reset(request)

        else:
            # next chunk
            self._response.next_chunk += 1

    def get_response(self) -> StartTransferResponse:

        if self._response.status == StartTransferResponseStatus.TRANSFER:
            try:
                data = self._chunk_generator.__next__()
                self._response.hash = hashlib.md5(data).digest()[0:2]
                self._response.size += len(data)
                self._ll_sender.send(data)

            except StopIteration:
                # no more chunks available
                self._response.status = StartTransferResponseStatus.FINISHED

        return self._response


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger('hl_upload')

    coloredlogs.install(logger=log)

    log.info('uploader test')

    # test file
    test_src_file = pathlib.Path('/home/pi/.bashrc')
    test_dst_folder = pathlib.Path('/home/pi/')

    sender = LLSender()
    hl_upload = HLUpload(test_dst_folder, sender)

    # copy test file to upload folder
    test_dst_folder.joinpath(
        'upload', test_src_file.parts[-1]).write_bytes(test_src_file.read_bytes())

    request = StartTransferRequest(filename=test_src_file.parts[-1])

    hl_upload.set_request((request))

    response = hl_upload.get_response()

    received = bytes()

    while response.status != StartTransferResponseStatus.FINISHED:
        log.info(response)
        while True:
            test_chunk = sender.get_chunk()
            if test_chunk == TransferData():
                break
            log.info(test_chunk)
            received += test_chunk.data

        response = hl_upload.get_response()

    original = test_src_file.read_bytes()
    assert original == received, 'test failed'
