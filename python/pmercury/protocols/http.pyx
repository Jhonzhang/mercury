#cython: language_level=3, wraparound=False, cdivision=True, infer_types=True, initializedcheck=False, c_string_type=bytes, embedsignature=False

"""
 Copyright (c) 2019 Cisco Systems, Inc. All rights reserved.
 License at https://github.com/cisco/mercury/blob/master/LICENSE
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../')
from pmercury.protocols.protocol import Protocol


class HTTP(Protocol):

    def __init__(self, fp_database=None, config=None):
        # populate fingerprint databases
        self.fp_db = {}

        # configuration
        HTTP.all_headers = False
        if config == None or 'http' not in config:
            HTTP.case_insensitive_static_headers = set([b'upgrade-insecure-requests',b'dnt',b'accept-language',b'connection',
                                                        b'x-requested-with',b'accept-encoding',b'content-length',b'accept',
                                                        b'viewport-width',b'intervention',b'dpr',b'cache-control'])
            HTTP.case_sensitive_static_headers = set([b'content-type',b'origin'])
            HTTP.headers_data = [0,2]
            HTTP.contextual_data = {b'user-agent':'user_agent',b'host':'host',b'x-forwarded-for':'x_forwarded_for'}
        else:
            HTTP.case_insensitive_static_headers = set([])
            HTTP.case_sensitive_static_headers = set([])
            HTTP.headers_data = []
            HTTP.contextual_data = {}
            if 'case_insensitive_static_headers' in config['http']:
                if config['http']['case_insensitive_static_headers'] == ['*']:
                    HTTP.all_headers = True
                HTTP.case_insensitive_static_headers = set(map(lambda x: x.lower().encode(), config['http']['case_insensitive_static_headers']))
            if 'case_sensitive_static_headers' in config['http']:
                if config['http']['case_sensitive_static_headers'] == ['*']:
                    HTTP.all_headers = True
                HTTP.case_sensitive_static_headers = set(map(lambda x: x.encode(), config['http']['case_sensitive_static_headers']))
            if 'preamble' in config['http']:
                if 'method' in config['http']['preamble']:
                    HTTP.headers_data.append(0)
                if 'uri' in config['http']['preamble']:
                    HTTP.headers_data.append(1)
                if 'version' in config['http']['preamble']:
                    HTTP.headers_data.append(2)
                if '*' in config['http']['preamble']:
                    HTTP.headers_data = [0,1,2]
            if 'context' in config['http']:
                for c in config['http']['context']:
                    HTTP.contextual_data[c.encode()] = c.lower().replace('-','_')


    @staticmethod
    def proto_identify(data, offset, data_len):
        if data_len-offset < 16:
            return False
        if (data[offset]   == 71 and
            data[offset+1] == 69 and
            data[offset+2] == 84 and
            data[offset+3] == 32):
            return True
        return False


    @staticmethod
    def fingerprint(bytes data, unsigned int offset, unsigned int data_len):
        cdef list t_ = data[offset:].split(b'\x0d\x0a', 1)
        cdef list request = t_[0].split()
        if len(request) < 3:
            return None, None

        cdef list c = []
        for rh in HTTP.headers_data:
            c.append('(%s)' % request[rh].hex())

        if len(t_) == 1:
            return ''.join(c), None

        cdef bint http_ah = HTTP.all_headers
        cdef set http_cish = HTTP.case_insensitive_static_headers
        cdef set http_cssh = HTTP.case_sensitive_static_headers
        cdef dict http_ctx = HTTP.contextual_data
        cdef list headers = t_[1].split(b'\x0d\x0a')
        cdef bytes t0_
        cdef bytes t0_lower
        context = []
        for h_ in headers:
            if h_ == b'':
                break
            t0_ = h_.split(b'\x3a\x20',1)[0]
            t0_lower = t0_.lower()


            if http_ah:
                h_c = h_.hex()
            elif t0_lower in http_cish:
                h_c = h_.hex()
            elif t0_ in http_cssh:
                h_c = h_.hex()
            else:
                h_c = t0_.hex()

            c.append('(%s)' % h_c)
            if t0_lower in http_ctx:
                if b'\x3a\x20' in h_:
                    try:
                        context.append({'name':http_ctx[t0_lower], 'data':h_.split(b'\x3a\x20',1)[1].decode()})
                    except UnicodeDecodeError:
                        context.append({'name':http_ctx[t0_lower], 'data':h_.split(b'\x3a\x20',1)[1].hex()})
                else:
                    context.append({'name':http_ctx[t0_lower], 'data':''})

        return ''.join(c), context


    def get_human_readable(self, fp_str_):
        t_ = [bytes.fromhex(x[1:]) for x in fp_str_.split(')')[:-1]]
        try:
            fp_h = [{'method':t_[0].decode()},{'version':t_[1].decode()}]
        except:
            fp_h = [{'method':t_[0].hex()},{'version':t_[1].hex()}]
        for i in range(2, len(t_)-1):
            field = t_[i].split(b': ',1)
            if len(field) == 2:
                try:
                    fp_h.append({field[0].decode(): field[1].decode()})
                except:
                    fp_h.append({field[0].hex(): field[1].hex()})
            else:
                try:
                    fp_h.append({field[0].decode(): ''})
                except:
                    fp_h.append({field[0].hex(): ''})
        return fp_h
