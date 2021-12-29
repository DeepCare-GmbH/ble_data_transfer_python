
import logging
from typing import List
import coloredlogs
import hashlib
from ble_data_transfer_python.gen.deepcare.transfer_data import TransferData
import itertools
import time

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
        it = iter(bytes(string, 'utf-8'))

        # determine payload size
        payload_size = self._mtu - PAYLOAD_HEADER_SIZE

        # split data now - create first slice
        item = bytes(itertools.islice(it, payload_size))
        while len(item):
            assert (len(item) <= payload_size), 'payload size error'
            # add slice
            result.append(item)
            # generate next slice
            item = bytes(itertools.islice(it, payload_size))

        return result


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger('tranceiver')

    coloredlogs.install(logger=log)

    log.info('tranceiver test')

    sender = Sender()

    s1000 = 'Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ' \
        'ut labore et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea' \
        ' rebum. Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet. Lorem ipsum dolor '\
        'sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna '\
        'aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd '\
        'gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet. Lorem ipsum dolor sit amet, consetetur '\
        'sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam '\
        'voluptua. At vero eos et accusam et justo duo dolores et ea rebum. Stet clita kasd gubergren, no sea takimata '\
        'sanctus est Lorem ipsum dolor sit amet. Duis autem vel eum iriure dolor in hendrerit in vulputate velit esse '\
        'molestie consequat, vel illum dolore eu feu'

    log.info(f'test data contains {len(s1000)} chars')
    data = sender.send_string(s1000)
    log.info(f'this leads to {len(data)} transfer chunks')

    receiver = Receiver()

    # for item in data:
    #     remaining = receiver.new_chunk(item)
    #     log.info(remaining)

    # if remaining == 0:
    #     r1000 = receiver.get_as_string

    #     if (r1000 == s1000):
    #         log.info('received == send')
    #     else:
    #         log.error('received != send')

    # else:
    #     log.error('receive error')
