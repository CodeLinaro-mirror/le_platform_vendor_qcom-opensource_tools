#!/usr/bin/env python
# Copyright (c) 2020, The Linux Foundation. All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 and
# only version 2 as published by the Free Software Foundation.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import optparse
import sys
import os
import json
import math
import string
import codecs

#from typing import List
from collections import OrderedDict

DEBUG_LEVEL = 0
DEFAULT_HEX = 0
DEBUG_check_string_bitfield_is_1 = 0
DEBUG_get_header_str = 0
BITS_IN_CHAR = 8
DEBUG_POST_PROCESS = 2

CONFIG_PREPEND_ZEROES_TO_MSB = True

_BLOCKSIZE_STR_ = "blockSize"
_NUMSETS_STR_ = "numSets"
_ASSOCIATIVITY_STR_ = "associativity"
_CACHETYPELIST_STR_ = "cacheTypes"
_STRUCTURE_STR_ = "structure"
_PARENT_STR_ = "parent"
_FIELDS_STR_ = "fields"
_BITFIELD_STR_ = "bitfield"
_NAME_STR_ = "name"
_HEX_STR_ = "hex"
_POST_PROCESS_STR_ = "post_process"
_SUBCACHE_STR_ = "subCache"
_OFFSET_STR_ = "offset"
_NEXT_STR_ = "next"


class Field():
    def __init__(self, Dict):
        self.name = Dict[_NAME_STR_]
        self.bitfield = Dict[_BITFIELD_STR_]
        if _HEX_STR_ in Dict.keys() and int(Dict[_HEX_STR_]) == 1:
            self.displayBase = 16
        else:
            self.displayBase = 10
        if _POST_PROCESS_STR_.replace(' ', '_').lower() in [k.replace(' ', '_').lower() for k in Dict.keys()]:
            dict_ordered = OrderedDict(Dict)
            i = [k.replace(' ', '_').lower() for k in dict_ordered.keys()].index(
                _POST_PROCESS_STR_.replace(' ', '_').lower())
            self.post_process_list = dict_ordered[dict_ordered.keys()[i]]

        else:
            self.post_process_list = None

    def get_field_width(self):
        return max(self.get_name_width(), self.get_bitfield_width())

    def get_name_width(self):
        return len(self.name.strip())

    def get_post_processed_width(self, width):
        for operation in self.post_process_list:
            for operator in operation.keys():
                if "<<" in operator:
                    try:
                        width = width + eval(str(operation[operator]))
                    except TypeError:
                        sys.stderr.write(str(operation[operator]) + '\n')
                elif ">>" in operator:
                    try:
                        width = width - eval(str(operation[operator]))
                    except TypeError:
                        sys.stderr.write(str(operation[operator]) + '\n')
                elif "sign_extend" in operator.strip().lower().replace(' ', '_'):
                    try:
                        extended_width = eval(str(operation[operator]))  # type: int
                        width = extended_width if (extended_width > width) else width
                    except TypeError:
                        sys.stderr.write(str(operation[operator]) + '\n')
        return width

    def get_bitfield_width(self):
        display_width = 0
        if DEBUG_LEVEL >= 2:
            print "func: get_bitfield_width"
            print "    : name = " + self.name
            print "    : list = " + str(self.get_bitfield_list())
            print "    : width = " + str(len(self.get_bitfield_list()))
            print "    : displayBase = " + str(self.displayBase)
        width = len(self.get_bitfield_list())  # no. of bits in the field
        if self.post_process_list is not None:
            width = self.get_post_processed_width(width)

        if self.displayBase == 16:
            display_width = int((width + 3) / 4)
        else:
            display_width = int(math.ceil(math.log10((1 << width))))
        if DEBUG_LEVEL >= 2:
            print "    : display_width = " + str(display_width)
        return display_width

    def post_process_value(self, res, set_num=None, way_num=None):
        for operation in self.post_process_list:
            for operator in operation.keys():
                if '<<' in operator:
                    try:
                        res = res << eval(str(operation[operator]))
                    except TypeError:
                        sys.stderr.write(str(operation[operator]) + '\n')
                elif '>>' in operator:
                    try:
                        res = res >> eval(str(operation[operator]))
                    except TypeError:
                        sys.stderr.write(str(operation[operator]) + '\n')
                elif '|' in operator or '&' in operator:
                    try:
                        operand = 0

                        # find whether set or way
                        if 'set' in [k.strip().lower() for k in operation[operator].keys()]:
                            src = set_num
                        elif 'way' in [k.strip().lower() for k in operation[operator].keys()]:
                            src = way_num

                        # extract the bitfield
                        try:
                            bf = operation[operator].values()[0]
                        except:
                            sys.stderr.write('could not interpret bitfield for operator ' + str(
                                operator) + ' in post-process-list ' + str(
                                self.post_process_list) + ' for field ' + self.name)
                            exit(-1)
                        for i in range(min([int(k) for k in bf.split(':')]), max([int(k) for k in bf.split(':')]) + 1):
                            if ((1 << i) & src): operand = (operand + (1 << i))

                        res = eval(str(res) + operator + str(operand))
                    except:
                        sys.stderr.write('Error occurred in post_process list for field:' + self.name + '\n')
                        exit(-1)
                elif 'sign_extend' in operator.strip().lower().replace(' ', '_'):
                    try:
                        extended_width = eval(str(operation[operator]))  # type: int
                        res = (((1 << extended_width) - 1) & res) if (((1 << extended_width) - 1) >= res) else res
                    except:
                        sys.stderr.write(str(operation[operator]) + '\n')
        return res

    def get_aligned_name(self, str_type=None):
        if str_type is 'header':
            return self.get_width_string(str_type='header').format(self.name.replace(' ', '_'))
        else:
            return self.get_width_string().format(self.name.replace(' ', '_'))

    def get_width_string(self, str_type=None):
        if CONFIG_PREPEND_ZEROES_TO_MSB and str_type is not 'header' and self.post_process_list is not None:
            return '{:0>' + str(self.get_field_width()) + '}'
        else:
            return '{:>' + str(self.get_field_width()) + '}'

    def get_width_hex_string(self):
        if CONFIG_PREPEND_ZEROES_TO_MSB:
            return '{:0>' + str(self.get_field_width()) + 'x}'
        else:
            return '{:>' + str(self.get_field_width()) + 'x}'

    def get_bitfield_list(self):
        bitfield_list = []
        field_list = self.bitfield.split(',')
        for f in field_list:
            if not f.split():
                continue
            if f.find(':') == -1:
                bitfield_list.append(int(eval(f)))
            else:
                nums = f.split(':')
                num1 = int(eval(nums[0]))
                num2 = int(eval(nums[1]))
                for i in range(min(num1, num2), max(num1, num2) + 1):
                    bitfield_list.append(i)
        return bitfield_list

    def get_aligned_bitfield(self, data, set_num=None, way_num=None):
        res = 0
        bitfield_list = self.get_bitfield_list()  # type: List[Field]
        bitfield_list.sort()
        for i in range(len(bitfield_list)):
            if check_string_bitfield_is_1(data, bitfield_list[i]):
                res = res + (1 << i)
        if self.post_process_list:
            res = self.post_process_value(res, set_num, way_num)
        if self.displayBase == 16:
            width_string = self.get_width_hex_string()
        else:
            width_string = self.get_width_string()
        ret_str = width_string.format(res)
        if DEBUG_LEVEL == -1:
            print ret_str
        return ret_str


def check_string_bitfield_is_1(s, bf):
    ret_val = 0
    lsb = 0
    msb = 0
    for i in range(0, len(s)):
        lsb = BITS_IN_CHAR * i
        msb = lsb + BITS_IN_CHAR - 1
        if msb >= bf >= lsb:
            if ord(s[i]) & (1 << (bf % BITS_IN_CHAR)):
                ret_val = 1
            break
    if DEBUG_check_string_bitfield_is_1:
        sys.stderr.write("func: check_string_bitfield_is_1: string=" + ' '.join(
            '{:02x}'.format(ord(ch)) for ch in s) + ' bitfield=' + str(bf) + ' res=' + str(ret_val))
        sys.stderr.write("    : lsb = " + str(lsb))
        sys.stderr.write("    : msb = " + str(msb))
        sys.stderr.write("    : 1 << (bf % BITS_IN_CHAR) = " + str(1 << (bf % BITS_IN_CHAR)))
        sys.stderr.write("    : ord(s[i]) = " + str(ord(s[i])))
    return ret_val


def get_header_str(field_list):
    ret_str = ''
    for field in field_list:
        if DEBUG_get_header_str:
            sys.stderr.write(field.get_aligned_name())
        ret_str = ret_str + field.get_aligned_name(str_type='header') + ' '
    return ret_str


def verify_json_file_sanity(filename):
    ret_val = True
    with open(filename) as fd:
        data = fd.read().replace('\n', '')
        try:
            json.loads(data)
        except:
            sys.stderr.write("Error: Invalid json file: " + filename + "\n")
            exit(-1)
            ret_val = False
    return ret_val


def search_json_obj_for_attribute(jsonObj, cacheType, attribute):
    if DEBUG_LEVEL >= 3:
        print ("\n\nentered function " + "search_json_obj_for_attribute")
        print "jsonObj = " + "\n" + str(jsonObj)
        print "cacheType = " + cacheType
        print "attribute = " + str(attribute)

    ret_val = None
    dict_type = type({})
    if cacheType in jsonObj.keys():
        if type(jsonObj[cacheType]) == dict_type and _STRUCTURE_STR_ in jsonObj[cacheType].keys():
            try:
                if type(jsonObj[cacheType][_STRUCTURE_STR_]) == dict_type:
                    if attribute in jsonObj[cacheType][_STRUCTURE_STR_].keys():
                        ret_val = jsonObj[cacheType][_STRUCTURE_STR_][attribute]
                    elif _PARENT_STR_ in jsonObj[cacheType][_STRUCTURE_STR_].keys():
                        ret_val = jsonObj[jsonObj[cacheType][_STRUCTURE_STR_][_PARENT_STR_]][_STRUCTURE_STR_][attribute]
            except:
                if DEBUG_LEVEL >= 2:
                    print sys.exc_info()[0]
                ret_val = None
    return ret_val


def search_json_file_for_attribute(filename, target_cpu, cache_type, attribute, json_type):
    ret_val = None
    if DEBUG_LEVEL >= 3:
        print ("\n\nentered function " + "search_json_file_for_attribute")
        print "filename = " + filename
        print "targetCpu = " + target_cpu
        print "cacheType = " + cache_type
        print "attribute = " + str(attribute)
        print "json_type = " + json_type

    if json_type == "cpu":
        # we know that the cpu specific json file is sane
        with open(filename) as fd:
            cpu_data_obj = fd.read().replace('\n', '')
            cpu_data = json.loads(cpu_data_obj)
        ret_val = search_json_obj_for_attribute(cpu_data, cache_type, attribute)
    elif json_type == "soc":
        verify_json_file_sanity(filename)
        try:
            with open(filename) as fd:
                soc_data_obj = fd.read().replace('\n', '')
                soc_data = json.loads(soc_data_obj)
            for socCpu in soc_data.keys():
                if target_cpu.lower() == socCpu.lower():
                    ret_val = search_json_obj_for_attribute(soc_data[socCpu], cache_type, attribute)
        except:
            print sys.exc_info()[0]
            ret_val = None
    if DEBUG_LEVEL >= 2:
        print "retVal = " + str(ret_val)
    return ret_val


def search_for_json_file(filename):
    for f in os.listdir(os.path.join(os.path.dirname(os.path.realpath(__file__)), "json")):
        if f.lower() == (filename.lower() + ".json"):
            return os.path.abspath(os.path.join(os.path.join(os.path.dirname(os.path.realpath(__file__)), "json"), f))
    return None


def extract_element_from_file(filename, seek_offset, block_size, Set, set_max, Way, way_max):
    with open(filename, "rb") as fd:
        offset = seek_offset + Way * (set_max * block_size) + (Set * block_size)
        fd.seek(offset)
        elem = fd.read(block_size)
    return elem


def parse_cache_line(line, cache_fields, set_num=None, way_num=None):
    ret_str = ''
    for field in cache_fields:
        ret_str = ret_str + field.get_aligned_bitfield(line, set_num, way_num) + ' '
    return ret_str.rstrip()


def get_cache_fields(cpuDataFile, cacheType):
    fields = []
    verify_json_file_sanity(cpuDataFile)
    with open(cpuDataFile) as fd:
        cpu_data_obj = fd.read().replace('\n', '')
        cpu_data = json.loads(cpu_data_obj)
    try:
        if type(cpu_data[cacheType][_FIELDS_STR_]) == type([]):
            for obj in cpu_data[cacheType][_FIELDS_STR_]:
                fields.append(Field(obj))
    except KeyError:
        sys.stderr.write("Cannot find any 'fields' key in cache description, dumping binary data\n")
        for i in range(int(cpu_data[cacheType][_STRUCTURE_STR_][_BLOCKSIZE_STR_]) / 4):  # Display groups of 4 Bytes
            fields.append(
                Field(
                    {"name": "{:>8x}".format(i*4),
                     "bitfield": "{}:{}".format(BITS_IN_CHAR * 4 * i, (BITS_IN_CHAR * 4 * (i + 1)) - 1), "hex": "1"}))
    return fields


def get_cache_structure(cpu_data_file, target_cpu, cache_type, opt_num_sets,
                        opt_associativity, opt_soc):
    num_sets = 0
    associativity = 0
    block_size = 0
    offset = 0

    # num sets
    if opt_num_sets:
        num_sets = int(opt_num_sets)
    elif opt_soc and search_for_json_file(opt_soc) and search_json_file_for_attribute(search_for_json_file(opt_soc),
                                                                                      target_cpu,
                                                                                      cache_type, _NUMSETS_STR_, "soc"):
        num_sets = search_json_file_for_attribute(search_for_json_file(opt_soc), target_cpu, cache_type, _NUMSETS_STR_,
                                                  "soc")
    else:
        num_sets = search_json_file_for_attribute(cpu_data_file, target_cpu, cache_type, _NUMSETS_STR_, "cpu")
    if isinstance(num_sets, basestring):
        try:
            num_sets = eval(num_sets)
        except:
            sys.stderr.write(
                "Cannot evaluate property:" + _NUMSETS_STR_ + ' cache:' + cache_type + ' cpu:' + target_cpu + '\n')
            exit(-1)
    # associativity
    if opt_associativity:
        associativity = int(opt_associativity)
    elif opt_soc and search_for_json_file(opt_soc) and search_json_file_for_attribute(search_for_json_file(opt_soc),
                                                                                      target_cpu,
                                                                                      cache_type, _ASSOCIATIVITY_STR_,
                                                                                      "soc"):
        associativity = search_json_file_for_attribute(search_for_json_file(opt_soc), target_cpu, cache_type,
                                                       _ASSOCIATIVITY_STR_, "soc")
    else:
        associativity = search_json_file_for_attribute(cpu_data_file, target_cpu, cache_type, _ASSOCIATIVITY_STR_,
                                                       "cpu")
    if isinstance(associativity, basestring):
        try:
            associativity = eval(associativity)
        except:
            sys.stderr.write(
                'Cannot evaluate property:' + _ASSOCIATIVITY_STR_ + ' cache:' + cache_type + ' cpu:' + target_cpu + '\n')
            exit(-1)

    # number of bytes in each dump element
    block_size = search_json_file_for_attribute(cpu_data_file, target_cpu, cache_type, _BLOCKSIZE_STR_, "cpu")
    if isinstance(block_size, basestring):
        try:
            block_size = eval(block_size)
        except:
            sys.stderr.write(
                "Cannot evaluate property:" + _BLOCKSIZE_STR_ + ' cache:' + cache_type + ' cpu:' + target_cpu + '\n')
            exit(-1)

    is_sub_cache = search_json_file_for_attribute(cpu_data_file, target_cpu, cache_type, _SUBCACHE_STR_, "cpu")
    if is_sub_cache == 'True':
        offset = search_json_file_for_attribute(cpu_data_file, target_cpu, cache_type, _OFFSET_STR_, "cpu")
        if isinstance(offset, basestring):
            try:
                offset = eval(offset)
            except:
                sys.stderr.write("Cannot evaluate property:" + _OFFSET_STR_ +
                                 ' cache:' + cache_type + ' cpu:' + target_cpu + '\n')
                exit(-1)

    return block_size, num_sets, associativity, offset


def cache_dump_parse(input_filename, output_filename, target_cpu, cpu_data_file, seek_offset, cache_type, opt_num_sets,
                     opt_associativity, opt_soc):
    with open(cpu_data_file) as fd:
        cpu_data_obj = fd.read().replace('\n', '')
        original_stdout = sys.stdout
        original_output_filename = output_filename
    done = False

    while not done:
        output_filename = original_output_filename
        # Get the output file handle
        if output_filename is not None:
            output_filename = output_filename + "_" + cache_type[19:]
            sys.stdout = open(output_filename, 'w+')

        # Get the cache structure: sets, ways, Bytes/line
        (block_size, num_sets, associativity, offset) = get_cache_structure(cpu_data_file, target_cpu,
                                                                            cache_type, opt_num_sets, opt_associativity,
                                                                            opt_soc)

        start_offset = seek_offset + offset

        try:
            total_bytes = block_size * num_sets * associativity
        except TypeError:
            sys.stderr.write('Type block_size    = ' + str(type(block_size)) + '\n')
            sys.stderr.write('Type num_sets      = ' + str(type(num_sets)) + '\n')
            sys.stderr.write('Type associativity = ' + str(type(associativity)) + '\n')
            exit(-1)

        # print cache structure information
        sys.stderr.write("\n" + "CPU: " + target_cpu)
        sys.stderr.write("\n" + "CacheType: " + cache_type)
        sys.stderr.write("\n" + _BLOCKSIZE_STR_ + ": " + str(block_size))
        sys.stderr.write("\n" + _NUMSETS_STR_ + ": " + str(num_sets))
        sys.stderr.write("\n" + _ASSOCIATIVITY_STR_ + ": " + str(associativity))
        sys.stderr.write("\n" + "Total cache size" + ": " + str(total_bytes))
        sys.stderr.write("\n" + "Input File: " + input_filename)
        sys.stderr.write("\n" + "Seek Offset: " + str(seek_offset))
	sys.stderr.write("\n" + "Start Offset: " + str(start_offset))
        sys.stderr.write("\n" + "Output File: " + output_filename if output_filename is not None else "stdout")
        sys.stderr.write("\n")

        # Get the individual fields of the cache line
        cache_fields = get_cache_fields(cpu_data_file, cache_type)

        # Check if we exceed the file bounds
        if (start_offset + total_bytes) > os.path.getsize(input_filename):
            sys.stderr.write("Error: exceeding file boundary for cache-type " + cache_type + "\n")
            sys.exit(-1)

        header_str = get_header_str(cache_fields)
        print('Way  Set ' + header_str)

        for way in range(associativity):
            for Set in range(num_sets):
                elem = extract_element_from_file(input_filename, start_offset, block_size, Set, num_sets, way, associativity)
                field_str = parse_cache_line(elem, cache_fields, Set, way)
                print '{:>3}'.format(str(way)) + ' ' + '{:>4}'.format(
                    str(Set)) + ' ' + field_str

        # restore stdout
        if output_filename is not None:
            sys.stdout = original_stdout

        res = search_json_file_for_attribute(cpu_data_file, target_cpu, cache_type, _NEXT_STR_, "cpu")
        if res is None:
            done = True
        else:
            cache_type = res


def main():
    input_filename = ''
    output_filename = ''
    target_cpu = ''
    seek_offset = 0
    cache_type = ''

    # Define cmd-line args
    parser = optparse.OptionParser()
    parser.add_option("-i", "--input", dest="input_filename",
                      help="input binary dump file")
    parser.add_option("-o", "--output", dest="output_filename",
                      help="output file")
    parser.add_option("-c", "--cpu", dest="target_cpu",
                      help="CPU name")
    parser.add_option("-s", "--seek", dest="seek_offset",
                      help="offset within input file(in Bytes)")
    parser.add_option("-t", "--type", dest="cache_type",
                      help="cache type")
    parser.add_option("--sets", dest="num_sets",
                      help="number of sets(cache index lines)")
    parser.add_option("--ways", dest="associativity",
                      help="number of ways(cache associativity)")
    parser.add_option("--soc", dest="soc",
                      help="SOC number(for cache configuration detection)")

    (options, args) = parser.parse_args()

    # Check input file sanity
    if not options.input_filename or not os.path.isfile(options.input_filename):
        sys.stderr.write("Error: incorrect input file\n")
        sys.exit(-1)
    else:
        input_filename = options.input_filename
    if DEBUG_LEVEL >= 1:
        sys.stderr.write("input_filename = " + input_filename + "\n")

    # Check output file sanity
    if options.output_filename is None:
        sys.stderr.write("No output file provided; writing to stdout\n")
    else:
        output_dirname = os.path.dirname(os.path.abspath(options.output_filename))
        if not os.access(output_dirname, os.W_OK):
            sys.stderr.write("Error: No write permissions for output file\n")
            sys.exit(-1)
    if DEBUG_LEVEL >= 1:
        sys.stderr.write("output_filename = " + str(options.output_filename) + "\n")

    # Check CPU sanity
    if options.target_cpu is None:
        sys.stderr.write("Error: Please provide a valid CPU\n")
        sys.exit(-1)
    cpu_found = 0
    cpu_data_file = search_for_json_file(options.target_cpu)
    if cpu_data_file: cpu_found = 1
    if not cpu_found:
        sys.stderr.write("Error: CPU not supported\n")
        sys.exit(-1)
    if DEBUG_LEVEL >= 1:
        sys.stderr.write("cpu_data_file = " + cpu_data_file + "\n")

    # Check validity of seek offset
    try:
        seek_offset_int = eval(options.seek_offset)
    except:
        sys.stderr.write("seek offset is not an integer, please see usage for details")
        sys.exit(-1)
    if os.path.getsize(input_filename) < seek_offset_int:
        sys.stderr.write("Error: Seek offset exceeds file size\n")
        if DEBUG_LEVEL >= 2:
            sys.stderr.write("filesize of " + str(input_filename) + " = " + str(os.path.getsize(input_filename)) + "\n")
            sys.stderr.write("offset = " + str(options.seek_offset) + "\n")
            sys.stderr.write("type filesize = " + str(type(os.path.getsize(input_filename))))
        sys.exit(-1)
    else:
        seek_offset = seek_offset_int
    if DEBUG_LEVEL >= 2:
        sys.stderr.write("offset = " + str(seek_offset) + "\n")

    # Check whether the cache type is supported by the particular CPU
    if options.cache_type is None:
        sys.stderr.write("Error: Please provide a valid cache type\n")
        sys.exit(-1)
    with open(cpu_data_file) as fd:
        cpu_data_obj = fd.read().replace('\n', '')
        try:
            cpu_data = json.loads(cpu_data_obj)
        except:
            sys.stderr.write("Error(1): Invalid json file: " + cpu_data_file + "\n")
            sys.exit(-1)
        cache_types = cpu_data.keys()
    cache_type_found = 0
    for c in cache_types:
        if c.lower() == options.cache_type.lower():
            cache_type_found = 1
            cache_type = c
            break
    if not cache_type_found:
        sys.stderr.write("Error: Cache type " + options.cache_type + " not supported by CPU\n")
        sys.stderr.write("Cache types supported are\n")
        sys.stderr.write("\n".join(cache_types) + "\n")
        sys.exit(-1)

    # Now that args have been verified, call the parser function
    cache_dump_parse(input_filename, options.output_filename, options.target_cpu, cpu_data_file, seek_offset, cache_type,
                     options.num_sets, options.associativity, options.soc)


if __name__ == "__main__":
    main()
