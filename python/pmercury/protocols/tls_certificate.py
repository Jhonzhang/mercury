"""
 Copyright (c) 2019 Cisco Systems, Inc. All rights reserved.
 License at https://github.com/cisco/mercury/blob/master/LICENSE
"""

import os
import sys
import base64

# TLS helper classes
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../')
from pmercury.protocols.protocol import Protocol
from pmercury.utils.tls_utils import *
from pmercury.utils.tls_constants import *
from pmercury.utils.cert_constants import *


class TLS_Certificate(Protocol):
    def __init__(self):
        self.fp_db = None


    @staticmethod
    def proto_identify(data, offset):
        if (data[offset]   == 22 and
            data[offset+1] ==  3 and
            data[offset+2] <=  3 and
            data[offset+5] == 11):
            return True
        return False


    @staticmethod
    def proto_identify_hs(data, offset):
        if (data[offset]   == 11 and
            data[offset+1] ==  0 and
            data[offset+4] ==  0 and
            data[offset+7] ==  0):
            return True
        return False


    @staticmethod
    def proto_identify_sh(data, offset):
        if (data[offset]    == 22 and
            data[offset+1]  ==  3 and
            data[offset+2]  <=  3 and
            data[offset+5]  ==  2 and
            data[offset+9]  ==  3 and
            data[offset+10] <=  3):
            return True
        return False


    @staticmethod
    def fingerprint(data, app_offset, data_len):
        data_len = len(data)
        offset = app_offset

        if (data[offset]    == 22 and
            data[offset+1]  ==  3 and
            data[offset+2]  <=  3 and
            data[offset+5]  ==  2 and
            data[offset+9]  ==  3 and
            data[offset+10] <=  3):
            offset += 9+int(data[offset+6:offset+9].hex(),16)
            if offset >= data_len:
                return None, None

        if (data[offset]   == 22 and
            data[offset+1] ==  3 and
            data[offset+2] <=  3 and
            data[offset+5] == 11 and
            data[offset+6] ==  0):
            offset += 5
        elif (data[offset]   == 11 and
              data[offset+1] ==  0 and
              data[offset+4] ==  0 and
              data[offset+7] ==  0):
            pass
        else:
            return None, None

        certificates_length = int(data[offset+4:offset+7].hex(),16)
        offset += 7
        if offset >= data_len:
            return None, None

        certs = []
        while offset < certificates_length:
            cert_len = int(data[offset:offset+3].hex(),16)
            offset += 3
            if offset >= data_len:
                return certs, None

            certs.append(base64.b64encode(data[offset:offset+cert_len]).decode())

            offset += cert_len
            if offset >= data_len:
                return certs, None

        return certs, None


    @staticmethod
    def fingerprint_old(data, app_offset, data_len):
        data = data[app_offset:]

        sh = False
        if TLS_Certificate.proto_identify_sh(data,0):
            data = data[9+int(data[6:9].hex(),16):]
            if len(data) == 0:
                return None, None
            sh = True

        if TLS_Certificate.proto_identify(data,0):
            offset = 5
        elif TLS_Certificate.proto_identify_hs(data,0):
            offset = 0
        else:
            return None, None

        certificates_length = int(data[offset+4:offset+7].hex(),16)
        data_len = len(data)
        offset += 7
        if offset >= data_len:
            return None, None

        certs = []
        while offset < certificates_length:
            cert_len = int(data[offset:offset+3].hex(),16)
            offset += 3
            if offset >= data_len:
                return certs, None

            certs.append(base64.b64encode(data[offset:cert_len]).decode())

            offset += cert_len
            if offset >= data_len:
                return certs, None

        return certs, None


    def get_human_readable(self, fp_str_):
        fp_h = []
        for cert_ in fp_str_:
            cert = base64.b64decode(cert_)

            cert_json = self.cert_parser(cert)

            fp_h.append(cert_json)
        return fp_h


    def cert_parser(self, cert):
        out_ = {}

        offset = 10

        # parse version
        _, _, value, offset = self.parse_tlv(cert, offset)
        if offset == None:
            return out_
        value = value.hex()
        if value in cert_versions:
            value = cert_versions[value]
        out_['version'] = value

        # parse serial number
        _, _, value, offset = self.parse_tlv(cert, offset)
        if offset == None:
            return out_
        out_['serial_number'] = value.hex()

        # skip signature
        _, _, value, offset = self.parse_tlv(cert, offset)
        if offset == None:
            return out_

        # parse issuer
        _, _, value, offset = self.parse_tlv(cert, offset)
        if offset == None:
            return out_
        out_['issuer'] = self.parse_rdn_sequence(value)

        # parse validity
        _, _, value, offset = self.parse_tlv(cert, offset)
        if offset == None:
            return out_
        out_['validity'] = self.parse_validity(value)

        # parse subject
        _, _, value, offset = self.parse_tlv(cert, offset)
        if offset == None:
            return out_
        out_['subject'] = self.parse_rdn_sequence(value)

        # skip subject_public_key_info
        _, _, value, offset = self.parse_tlv(cert, offset)
        if offset == None:
            return out_

        return out_


    def parse_validity(self, data):
        offset = 0
        _, _, not_before, offset = self.parse_tlv(data, offset)
        if offset == None:
            return None

        try:
            out_ = {'not_before': not_before.decode()}
        except:
            out_ = {'not_before': not_before.hex()}

        _, _, not_after, offset = self.parse_tlv(data, offset)
        if offset == None:
            return out_

        try:
            out_['not_after'] = not_after.decode()
        except:
            out_['not_after'] = not_after.hex()

        return out_

    def parse_rdn_sequence_item(self, data):
        _, _, value, _ = self.parse_tlv(data, 0)
        if value == None:
            return None

        offset = 0
        _, _, id_, offset = self.parse_tlv(value, offset)
        if offset == None:
            return None
        tag_, _, val_, offset = self.parse_tlv(value, offset)
        if offset == None:
            return None

        id_ = id_.hex()
        if id_.startswith('5504') and len(id_) == 6 and id_[4:6] in cert_attribute_types:
            id_ = cert_attribute_types[id_[4:6]]

        if tag_ == 19 or tag_ == 12: # printable string
            val_ = val_.decode()
        else:
            val_ = val_.hex()

        return {id_: val_}


    def parse_rdn_sequence(self, data):
        offset = 0
        len_   = len(data)

        items = []
        _, _, value, offset = self.parse_tlv(data, offset)
        while offset != None:
            item_ = self.parse_rdn_sequence_item(value)
            if item_ != None:
                items.append(item_)
            _, _, value, offset = self.parse_tlv(data, offset)

        return items


    def parse_tlv(self, data, offset):
        if len(data) < offset+3:
            return None, None, None, None

        tag_ = data[offset]
        len_ = data[offset+1]
        if len_ >= 128:
            num_octets = len_ - 128
            if num_octets <= 0:
                return None, None, None, None
            len_ = int(data[offset+2:offset+2+num_octets].hex(),16)
            offset += num_octets
        val_ = data[offset+2:offset+2+len_]

        return tag_, len_, val_, offset+2+len_


    def proc_identify(self, fp_str_, context_, dst_ip, dst_port, list_procs=5):
        return None

