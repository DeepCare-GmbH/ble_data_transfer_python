#!/usr/bin/env python3

# Class providing low level reception of chunked data.
# Michael Katzenberger
# 29.12.2021

import hashlib
import time
from enum import Enum
from typing import List

from ble_data_transfer_python.gen.deepcare.transfer_data import TransferData


class LLReceiverError(Enum):
    NONE = 0,
    WRONG_HASH = 1,
    WRONG_SEQUENCE = 2,


class LLReceiver():
    """Class providing reception of chunked data.
    """

    def __init__(self) -> None:
        """Constructor.
        """

        # number of chunks expected
        self._remaining_chunks = 0
        # received data
        self._data = bytes()
        # time stamp the data transfer was initiated, contains duration after transfer
        self._timestamp = 0.0
        # flag to indicate that new unread data are available
        self.new_data = False
        self.error = LLReceiverError.NONE

    def _reset(self, num_of_chunks: int) -> None:
        """Reset the transfer.

        Setup all internal variables to begin a new reception.

        Args:
            num_of_chunks (int): number of chunks to receive
        """

        self._remaining_chunks = num_of_chunks
        self._data = bytes()
        self._timestamp = time.time()
        self.new_data = False
        self.error = LLReceiverError.NONE

    def new_chunk(self, chunk: TransferData) -> int:
        """Consume received chunk.

        Args:
            chunk (TransferData): received chunk (protbuf)

        Returns:
            int: number of remaining chunks or
                 zero if reception is completed or
                 -1 in case of error
        """

        # very first chunk will reset the file reception
        if chunk.current_chunk == 0:
            self._reset(chunk.overall_chunks)

        # check for correct chunk sequence
        elif (self._remaining_chunks + chunk.current_chunk) != chunk.overall_chunks:
            self.error = LLReceiverError.WRONG_SEQUENCE
            return -1

        # calc and verify hash
        chunk_hash = hashlib.md5(bytes(chunk.data)).digest()[0:2]
        if chunk_hash != bytes(chunk.hash):
            self.error = LLReceiverError.WRONG_HASH
            return -1

        # join received byte list
        self._data += bytes(chunk.data)
        self._remaining_chunks -= 1

        # if last chunk than set new data flag
        if self._remaining_chunks == 0:
            # new data are now available
            self.new_data = True
            # after transfer time stamp contains the data transfer duration
            self._timestamp = time.time() - self._timestamp

        return self._remaining_chunks

    @property
    def transfer_duration(self) -> float:
        """Duration of last transfer.

        Returns:
            float: duration or zero if a reception is in progress
        """

        # if transfer is in progress return zero
        if self._remaining_chunks > 0:
            return 0.0

        # return the duration of the last transfer
        return self._timestamp

    @property
    def remaining(self) -> int:
        """Return the number of remaining chunks.

        Returns:
            int: remaining chunks or zero if reception is completed
        """

        return self._remaining_chunks

    @property
    def data(self) -> bytes:
        """Return received data.

        Returns:
            bytes: received data as byte class
        """

        self.new_data = False
        return self._data
