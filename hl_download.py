#!/usr/bin/env python3

# Class providing high level data reception
# Michael Katzenberger
# 30.12.2021

import hashlib
import logging
import pathlib
import time
from typing import Callable, List

import coloredlogs

from ble_data_transfer_python.gen.deepcare.messages import (
    StartTransferRequest, StartTransferResponse, StartTransferResponseStatus,
    Target)
from ble_data_transfer_python.ll_receiver import LLReceiver


class HLDownload:

    # file name to use for storing the download request
    DOWNLOAD_REQUEST_FILE = 'request.json'
    # base file name of the chunk files to use
    DOWNLOAD_CHUNK_BASE_NAME = 'chunk'

    def __init__(self, root_path: str, ll_receiver: LLReceiver, cb_finished: Callable[[pathlib.Path], None]) -> None:

        self._logger = logging.getLogger(self.__class__.__name__)
        coloredlogs.install(logger=self._logger)

        # take over low lever receiver
        self._ll_receiver = ll_receiver
        # take over the download finished callback
        self._cb_finished: Callable[[pathlib.Path], None] = cb_finished

        # ensure download folders exists
        self._download_path = pathlib.Path(root_path).joinpath('download')
        self._download_path.mkdir(parents=True, exist_ok=True)

        # current request
        self._request = StartTransferRequest()
        # current response
        self._response = StartTransferResponse()

        # time stamp the data transfer was initiated, contains duration after transfer
        self._timestamp = 0.0

        # check if a download was in progress and can be resumed
        self._resume_download()

    def _resume_download(self) -> None:
        """Internal function called during system startup to resume an ongoing download.
        """

        # search for previous request
        if self._download_path.joinpath(self.DOWNLOAD_REQUEST_FILE).is_file():
            # file found - read it
            with open(
                    file=self._download_path.joinpath(
                        self.DOWNLOAD_REQUEST_FILE),
                    mode='r',
                    encoding='utf-8') as request_file:
                try:
                    self._request.from_json(request_file.read())
                except:
                    self._logger.error(
                        'invalid json file - can not resume download')
                    # delete corrupt file
                    self._download_path.joinpath(
                        self.DOWNLOAD_REQUEST_FILE).unlink()
                    # remove possible download artifacts
                    self._delete_chunks()
                    return

            # call reset to setup response accordingly
            self._reset(self._request)

            # use number of already received chunks as next chunk number
            self._response.next_chunk = len(
                list(self._download_path.glob(f'{self.DOWNLOAD_CHUNK_BASE_NAME}*.bin')))

            # use creation date of request file as start time
            self._timestamp = self._download_path.joinpath(
                self.DOWNLOAD_REQUEST_FILE).stat().st_atime

            # use size of first chunk file (file name index 0) to calculate whole amount of already received bytes
            if self._response.next_chunk > 0:
                chunk_size = self._download_path.joinpath(
                    f'{self.DOWNLOAD_CHUNK_BASE_NAME}0.bin').stat().st_size
                self._response.size = chunk_size * self._response.next_chunk

            self._logger.info(
                'found running update: next chunk=%d. size=%d, duration=%f',
                self._response.next_chunk, self._response.size, self.transfer_duration)

        else:
            # no previous download in progress - delete possible artifacts
            self._delete_chunks()

    def _delete_chunks(self) -> None:
        """Internal function to delete all download artifacts after successful file download.
        """

        # erase all chunks files
        for item in self._download_path.glob(f'{self.DOWNLOAD_CHUNK_BASE_NAME}*.bin'):
            item.unlink()

    def _reset(self, request: StartTransferRequest):
        """Internal function to initiate a transfer depending on the request and internal condition.

        Args:
            request (StartTransferRequest): received transfer request
        """

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

        Setup all internal variables to begin a new transmission.
        """

        # if hash is different or no previous transfer was active
        # than a new transfer is requested
        if (self._request.hash != request.hash) or (self._response.status != StartTransferResponseStatus.TRANSFER):
            # reset for handling a new request
            self._reset(request)
            # save request to disk
            with open(
                    file=self._download_path.joinpath(
                        self.DOWNLOAD_REQUEST_FILE),
                    mode='w',
                    encoding='utf-8') as request_file:
                request_file.write(self._request.to_json())
            self._delete_chunks()

        self._logger.info('start transfer request received')
        self._logger.debug(request)

    def get_response(self) -> StartTransferResponse:
        """Get the transfer response.

        Returns:
            StartTransferResponse: current transfer response
        """

        self._logger.info('start transfer response requested')
        self._logger.debug(self._response)

        # check if transfer was requested which means that the chunk counter must be unequal zero
        if self._response.chunks == 0:
            self._response.status = StartTransferResponseStatus.ERROR
            self._logger.error(
                'number of chunks is zero: file transfer initiated ?')

        # check if more chunks were requested than available
        elif self._response.next_chunk > self._response.chunks:
            self._response.status = StartTransferResponseStatus.ERROR
            self._logger.error('non-existant chunk requested')

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
        """Internal function called after a file transfer has been finished.
        """

        # stop time
        self._timestamp = time.time() - self._timestamp

        # cat the the chunks into the final file and calculate the hash
        file_hash = hashlib.md5()
        file_name = self._download_path.joinpath(self._request.filename)
        with open(file_name, 'wb') as binary_out:
            for i in range(self._response.chunks):
                chunk_name = self._download_path.joinpath(
                    f'{self.DOWNLOAD_CHUNK_BASE_NAME}{i}.bin')
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

        # erase request file (which is the indicator of an running download )
        self._download_path.joinpath((self.DOWNLOAD_REQUEST_FILE)).unlink()

        # call user callback
        if self._response.status == StartTransferResponseStatus.FINISHED:
            # use received file in case of success
            self._cb_finished(file_name, self._request.target)
        else:
            # file reception was not successful
            self._cb_finished(None, Target.UNKNOWN)

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
