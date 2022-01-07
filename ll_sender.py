
import hashlib
import itertools
import logging
from typing import List

import coloredlogs

from ble_data_transfer_python.gen.deepcare.transfer_data import TransferData

PAYLOAD_HEADER_SIZE = 22


class Sender():

    def __init__(self, mtu=185) -> None:
        self._mtu = mtu

    def send_string(self, string: str) -> List[TransferData]:

        transfer_data: List[TransferData] = []

        # slice data into chunks of maximum payload
        split = self._split(string)

        # generate final protobuf list
        for index, item in enumerate(split):
            transfer_data.append(
                TransferData(
                    current_chunk=index,
                    overall_chunks=len(split),
                    hash=hashlib.md5(item).digest()[0:2],
                    data=item,
                )
            )

        return transfer_data

    def _split(self, string: str) -> List[bytes]:

        result: List[bytes] = []

        # generate iterator from data
        it_string = iter(bytes(string, 'utf-8'))

        # determine payload size
        payload_size = self._mtu - PAYLOAD_HEADER_SIZE

        # split data now - create first slice
        item = bytes(itertools.islice(it_string, payload_size))
        while len(item):
            assert (len(item) <= payload_size), 'payload size error'
            # add slice
            result.append(item)
            # generate next slice
            item = bytes(itertools.islice(it_string, payload_size))

        return result


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger('transceiver')

    coloredlogs.install(logger=log)

    log.info('transceiver test')

    sender = Sender()

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

    log.info('test data contains %d chars', len(S1000))
    data = sender.send_string(S1000)
    log.info('this leads to %d transfer chunks', len(data))
