#!/usr/bin/env python3

# Class providing high level data reception
# Michael Katzenberger
# 30.12.2021

import hashlib
import logging
import pathlib
from math import ceil
import time

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

        # time stamp the data transfer was initiated, contains duration after transfer
        self._timestamp = 0.0

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

        # take timestamp
        self._timestamp = time.time()

        # create generator
        self._chunk_generator = self._split(upload_file)

    def _split(self, file_name: pathlib.Path) -> bytes:

        with open(file_name, 'rb') as f_in:
            while True:
                data = f_in.read(self._chunk_size)
                yield data
                if len(data) != self._chunk_size:
                    break

    def set_request(self, request: StartTransferRequest) -> None:

        # empty hash starts a new request
        if not request.hash:

            # start new transfer with requested file
            self._reset(request)

        else:
            # check if more junks are read than available
            if self._response.next_chunk >= self._response.chunks:
                self._logger.error('no more chunks available')

            # next chunk
            self._response.next_chunk += 1

        self._logger.debug(self._request)

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
                # reset hash
                self._response.hash = bytes()
                # stop time
                self._timestamp = time.time() - self._timestamp

        # update transfer time
        self._response.duration = self.transfer_duration

        self._logger.debug(self._response)

        return self._response

    @property
    def transfer_duration(self) -> float:
        """Duration of last transfer.

        Returns:
            float: duration of file transfer in [s]
        """

        # if transfer in progress return time since start
        if self._response.status == StartTransferResponseStatus.TRANSFER:
            duration = time.time() - self._timestamp

        # return the duration of the last transfer
        elif self._response.status == StartTransferResponseStatus.FINISHED:
            duration = self._timestamp

        # in all other cases return zero
        else:
            duration = 0.0

        return round(duration, 2)


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger('hl_upload')

    coloredlogs.install(logger=log)

    log.info('uploader test')

    # test file
    test_src_file = pathlib.Path('/home/pi/.bashrc')
    test_dst_folder = pathlib.Path('/home/pi/')

    sender = LLSender()
    hl_upload = HLUpload(test_dst_folder, sender, 1024*2)

    # copy test file to upload folder
    test_dst_folder.joinpath(
        'upload', test_src_file.parts[-1]).write_bytes(test_src_file.read_bytes())

    test_request = StartTransferRequest(filename=test_src_file.parts[-1])

    hl_upload.set_request((test_request))

    received = bytes()

    test_response = hl_upload.get_response()

    for n in range(test_response.chunks):

        log.info('read file chunk %d ...', n)
        while True:
            test_chunk = sender.get_chunk()
            if test_chunk == TransferData():
                break
            log.info('transfer data: chunks %d/%d',
                     test_chunk.current_chunk+1, test_chunk.overall_chunks)
            received += test_chunk.data

        log.info('request next file chunk')
        test_request.hash = test_response.hash
        hl_upload.set_request((test_request))

        test_response = hl_upload.get_response()

    original = test_src_file.read_bytes()
    assert original == received, 'test failed'
