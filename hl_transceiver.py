#!/usr/bin/env python3

# Class providing high level data reception
# Michael Katzenberger
# 30.12.2021

import hashlib
import logging
import pathlib
import time
from typing import List

import coloredlogs

from ble_data_transfer_python.gen.deepcare.messages import (
    StartTransferRequest, StartTransferResponse, StartTransferResponseStatus)
from ble_data_transfer_python.ll_receiver import LLReceiver


class HLTransceiver():
    """Class providing reception of data.
    """

    def __init__(self, ll_receiver: LLReceiver, download_path: str) -> None:
        """Constructor.
        """

        self._logger = logging.getLogger(self.__class__.__name__)
        coloredlogs.install(logger=self._logger)

        # current request
        self._request = StartTransferRequest()
        # current response
        self._response = StartTransferResponse()

        # time stamp the data transfer was initiated, contains duration after transfer
        self._timestamp = 0.0

        # take over low lever receiver
        self._ll_receiver = ll_receiver
        # set callback if ll chunk was received
        self._ll_receiver.cb_new_data = self.add_chunk

        # ensure download path folder exists
        self._download_path = pathlib.Path(download_path).expanduser()
        self._download_path.mkdir(parents=True, exist_ok=True)

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

        self._logger.info('start transfer request received')
        self._logger.debug(request)

    def get_response(self) -> StartTransferResponse:
        """Get the transfer response.

        Returns:
            StartTransferResponse: current transfer response
        """

        self._logger.info('start transfer response requested')
        self._logger.debug(self._response)
        return self._response

    def add_chunk(self, chunk: List[bytes]) -> None:
        """Set as as callback in low level receiver.

        Executed each time a complete chunk was received from the app.
        All chunks are stored on disk in sequence.

        Args:
            chunk (List[bytes]): received chunk
        """

        # return hash
        self._response.hash = hashlib.md5(chunk).digest()

        # save chunk to disk
        file_name = self._download_path.joinpath(
            f'chunk{self._response.next_chunk}.bin')
        with open(file_name, 'wb') as chunk_file:
            chunk_file.write(chunk)

        # request next chunk
        self._response.next_chunk += 1

        self._logger.info(
            'new chunk (%d/%d) received (%s)', self._response.next_chunk, self._response.chunks, self._ll_receiver)

        # check if all chunks were received
        if self._response.next_chunk == self._response.chunks:
            self._transfer_finished()

        # update transfer time
        self._response.duration = self.transfer_duration
        self._response.size += len(chunk)

    def _transfer_finished(self):

        # stop time
        self._timestamp = time.time() - self._timestamp

        # cat the the chunks into the final file and calculate the hash
        file_hash = hashlib.md5()
        file_name = self._download_path.joinpath(self._request.filename)
        with open(file_name, 'wb') as binary_out:
            for i in range(self._response.chunks):
                chunk_name = self._download_path.joinpath(f'chunk{i}.bin')
                with open(chunk_name, 'rb') as fin:
                    chunk = fin.read()
                file_hash.update(chunk)
                binary_out.write(chunk)

        if file_hash.digest() == self._request.hash:
            self._response.status = StartTransferResponseStatus.FINISHED
            self._logger.info(
                '%s transferred in %0.1f s', self._request.filename, self._timestamp)

        else:
            self._response.status = StartTransferResponseStatus.ERROR
            self._logger.error('transfer finished - invalid hash')

    @property
    def transfer_duration(self) -> float:
        """Duration of last transfer.

        Returns:
            float: duration of file transfer in [s]
        """

        # if transfer in progress return time since start
        if self._response.status == StartTransferResponseStatus.TRANSFER:
            return time.time() - self._timestamp

        # return the duration of the last transfer
        if self._response.status == StartTransferResponseStatus.FINISHED:
            return self._timestamp

        # in all other cases return zero
        return 0.0

    @property
    def transferred_bytes(self) -> int:
        """Number of transferred bytes.

        Returns:
            int: number of transferred bytes so far
        """

        return self._response.size
