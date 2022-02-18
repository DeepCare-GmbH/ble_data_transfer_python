
import hashlib
import itertools
import logging
from math import ceil
from typing import List

import coloredlogs

from ble_data_transfer_python.gen.deepcare.transfer_data import TransferData


class LLSender():

    PAYLOAD_HEADER_SIZE = 22

    def __init__(self, mtu=185) -> None:

        # take over MTU
        self._mtu = mtu
        # transfer data instance
        self._transfer_data = TransferData()

    def send(self, data: List[bytes]):

        # determine payload size
        payload_size = self._mtu - self.PAYLOAD_HEADER_SIZE

        # reset transfer data
        self._transfer_data.current_chunk = -1
        self._transfer_data.overall_chunks = ceil(
            len(data) / payload_size)

        # create generator
        self._payload = self._split(data, payload_size)

    def get_chunk(self) -> TransferData:

        try:
            # return next chunk
            return self._payload.__next__()

        except StopIteration:
            # no more chunks available
            return TransferData()

    def _split(self, data: List[bytes], size: int) -> bytes:

        # generate iterator from data
        it_data = iter(data)

        while True:
            # get next chunk of data
            chunk = bytes(itertools.islice(it_data, size))

            if not chunk:
                # no more data available
                break

            # fill transfer data
            self._transfer_data.current_chunk += 1
            self._transfer_data.hash = hashlib.md5(chunk).digest()[0:2]
            self._transfer_data.data = chunk

            # return transfer data
            yield self._transfer_data


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger('ll_sender')

    coloredlogs.install(logger=log)

    log.info('transceiver test')

    MTU = 50

    sender = LLSender(mtu=MTU)

    # cSpell:disable
    S1000 = 'Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ' \
        'ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea' \
        ' rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet. Lorem ipsum dolor '\
        'sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna '\
        'aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd '\
        'gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet. Lorem ipsum dolor sit amet, consetetur '\
        'sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam '\
        'voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata '\
        'sanctus est Lorem ipsum dolor sit amet. Duis autem vel eum iriure dolor in hendrerit in vulputate velit esse '\
        'molestie consequat, vel illum dolore eu feu'
    # cSpell:enable

    log.info('test transmitting')

    sender.send(list(bytes(S1000, 'UTF-8')))

    expected_chunks = ceil(len(S1000) / (MTU - PAYLOAD_HEADER_SIZE))

    received = bytes()
    count = 0
    while True:
        test_chunk = sender.get_chunk()
        if test_chunk == TransferData():
            break
        print(test_chunk)
        received += test_chunk.data
        count += 1
        assert expected_chunks == test_chunk.overall_chunks, 'wrong number of chunks'

    assert count == expected_chunks, 'wrong number of chunks'
    assert bytes(S1000, 'UTF-8') == received, 'split error'

    log.info('test finished')
