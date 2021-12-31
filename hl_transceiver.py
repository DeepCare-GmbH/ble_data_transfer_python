#!/usr/bin/env python3

# Class providing high level data reception
# Michael Katzenberger
# 30.12.2021

import hashlib
import logging
import time
from enum import Enum
from typing import List

import coloredlogs

from ble_data_transfer_python.gen.deepcare.messages import (
    StartTransferRequest, StartTransferRequestDirection, StartTransferResponse,
    StartTransferResponseStatus, Target)
from ble_data_transfer_python.ll_receiver import LLReceiver


class HLTransceiver():
    """Class providing reception of data.
    """

    def __init__(self, ll_receiver: LLReceiver) -> None:
        """Constructor.
        """

        self._logger = logging.getLogger(self.__class__.__name__)
        coloredlogs.install(logger=self._logger)

        # current request
        self._request = StartTransferRequest()
        # current response
        self._response = StartTransferResponse()

        # received LL chunks
        self._chunks: List[bytes] = []
        # time stamp the data transfer was initiated, contains duration after transfer
        self._timestamp = 0.0

        self._hash = hashlib.md5()

        # take over low lever receiver
        self._ll_receiver = ll_receiver
        # set callback if ll chunk was received
        self._ll_receiver.cb_new_data = self.add_chunk

        self._logger.info('high level transceiver ready')

    def _reset(self, request: StartTransferRequest):

        # take over request
        self._request = request

        # create response for initial data transfer
        self._response = StartTransferResponse()
        # copy number of expected chunks
        self._response.chunks = request.chunks
        # copy expected filename
        self._response.filename = request.filename
        # ready for transfer
        self._response.status = StartTransferResponseStatus.TRANSFER

        # reset chunk list
        self._chunks = []
        # take timestamp
        self._timestamp = time.time()

    def set_request(self, request: StartTransferRequest) -> None:
        """Set the transfer request.

        Setup all internal variables to begin a new reception.

        Args:
            num_of_chunks (int): number of chunks to receive
        """

        # if hash is different or no previous transfer was active
        # than a new transfer is requested
        if (self._request.hash != request.hash) or (self._response.status != StartTransferResponseStatus.TRANSFER):
            self._reset(request)

        # set next chunk
        self._response.next_chunk = len(self._chunks)

        self._logger.info('start transfer request received')
        self._logger.debug(request)

    def get_response(self) -> StartTransferResponse:

        self._logger.info('start transfer response requested')
        self._logger.debug(self._response.next_chunk)
        return self._response

    def add_chunk(self, chunk: List[bytes]) -> None:

        # update hash
        self._hash.update(chunk)

        # save chunk to disk and store filename in list
        self._chunks.append(self._save_chunk(chunk))

        # request next chunk
        self._response.next_chunk += 1

        self._logger.info(
            f'new chunk ({self._response.next_chunk}/{self._response.chunks}) received ({self._ll_receiver})')

        # check if all chunks were received
        if self._response.next_chunk == self._response.chunks:
            self._transfer_finished()

    def _save_chunk(self, chunk: List[bytes]) -> str:
        file_name = f'chunk{len(self._chunks)}.bin'
        with open(file_name, 'wb') as f:
            f.write(chunk)
        return file_name

    def _transfer_finished(self):
        self._timestamp = time.time() - self._timestamp

        if self._hash.digest() == self._request.hash:
            with open(self._request.filename, 'wb') as fout:
                for item in self._chunks:
                    with open(item, 'rb') as fin:
                        fout.write(fin.read())
            self._response.status = StartTransferResponseStatus.FINISHED
            self._logger.info(
                f'{self._request.filename} transfered in {self._timestamp} s')
        else:
            self._response.status = StartTransferResponseStatus.ERROR
            self._logger.error('transfer finished - invalid hash')
