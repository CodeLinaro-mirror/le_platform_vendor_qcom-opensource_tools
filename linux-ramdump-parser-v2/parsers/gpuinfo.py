# Copyright (c) 2013-2015, 2020 The Linux Foundation. All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 and
# only version 2 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

from parser_util import register_parser, RamParser
from print_out import print_out_str
import linux_list
import traceback
import linux_radix_tree

# Global Configurations
ADRENO_DISPATCH_DRAWQUEUE_SIZE = 128
KGSL_PRIORITY_MAX_RB_LEVELS = 4
KGSL_MAX_PWRLEVELS = 10
MAX_CONTEXT_ID = 800
KGSL_MAX_POOLS = 4
PAGE_SIZE = 4096

def strhex(x): return str(hex(x))
def str_convert_to_kb(x): return str(x//1024) + 'kb'

@register_parser('--print-gpuinfo',
                 'print gpu driver related info', optional=True)
class GpuParser(RamParser):
    def __init__(self, dump):
        super(GpuParser, self).__init__(dump)

        # List of all sub-parsers as (func, info, outfile) tuples.
        self.parser_list_419 = [
            (self.parse_kgsl_data, "KGSL", 'gpuinfo.txt'),
            (self.parse_pwrctrl_data, "KGSL Power", 'gpuinfo.txt'),
            (self.parse_kgsl_mem, "KGSL Memory Stats", 'gpuinfo.txt'),
            (self.parse_rb_inflight_data, "Ringbuffer and Inflight Queues",
             'gpuinfo.txt'),
            (self.parse_dispatcher_data, "Dispatcher", 'gpuinfo.txt'),
            (self.parse_mutex_data, "KGSL Mutexes", 'gpuinfo.txt'),
            (self.parse_scratch_memory, "Scratch Memory", 'gpuinfo.txt'),
            (self.parse_memstore_memory, "Memstore", 'gpuinfo.txt'),
            (self.parse_context_data, "Open Contexts", 'gpuinfo.txt'),
            (self.parse_open_process_data, "Open Processes", 'gpuinfo.txt'),
            (self.parse_pagetables, "Process Pagetables", 'gpuinfo.txt'),
            (self.dump_gpu_snapshot, "GPU Snapshot", 'gpuinfo.txt'),
            (self.parse_fence_data, "Fences", 'gpu_sync_fences.txt'),
            (self.parse_open_process_mementry, "Open Process Mementries",
             'open_process_mementries.txt'),
        ]

        self.parser_list_54 = [
            (self.parse_kgsl_data_54, "KGSL", 'gpuinfo.txt'),
            (self.parse_pwrctrl_data, "KGSL Power", 'gpuinfo.txt'),
            (self.parse_kgsl_mem_54, "KGSL Memory Stats", 'gpuinfo.txt'),
            (self.parse_rb_inflight_data, "Ringbuffer and Inflight Queues",
             'gpuinfo.txt'),
            (self.parse_dispatcher_data_54, "Dispatcher", 'gpuinfo.txt'),
            (self.parse_mutex_data, "KGSL Mutexes", 'gpuinfo.txt'),
            (self.parse_scratch_memory_54, "Scratch Memory", 'gpuinfo.txt'),
            (self.parse_memstore_memory_54, "Memstore", 'gpuinfo.txt'),
            (self.parse_context_data, "Open Contexts", 'gpuinfo.txt'),
            (self.parse_open_process_data, "Open Processes", 'gpuinfo.txt'),
            (self.parse_pagetables, "Process Pagetables", 'gpuinfo.txt'),
            (self.dump_gpu_snapshot, "GPU Snapshot", 'gpuinfo.txt'),
            (self.parse_fence_data, "Fences", 'gpu_sync_fences.txt'),
            (self.parse_open_process_mementry, "Open Process Mementries",
             'open_process_mementries.txt'),
        ]

        self.rtw = linux_radix_tree.RadixTreeWalker(dump)

    def parse(self):
        if not self.ramdump.is_config_defined('CONFIG_QCOM_KGSL'):
            print_out_str(
                "No GPU support detected... Skipping GPU parser.")
            return

        if (self.ramdump.kernel_version == (0, 0, 0) or
           self.ramdump.kernel_version >= (5, 4, 0)):
            self.parser_list = self.parser_list_54
        elif self.ramdump.kernel_version >= (4, 19, 0):
            self.parser_list = self.parser_list_419
        else:
            print_out_str(
                "No GPU support detected for specified kernel version..."
                + " Skipping GPU parser.")
            return

        for subparser in self.parser_list:
            try:
                self.out = self.ramdump.open_file('gpu_parser/' + subparser[2],
                                                  'a')
                self.write(subparser[1].center(90, '-') + '\n')
                subparser[0](self.ramdump)
                self.writeln()
                self.out.close()
            except Exception:
                print_out_str("GPU info: Parsing failed in "
                              + subparser[0].__name__)
                print_out_str(traceback.format_exc())

    def write(self, string):
        self.out.write(string)

    def writeln(self, string=""):
        self.out.write(string + '\n')

    def print_context_data(self, ctx_addr):
        dump = self.ramdump
        context_id = str(dump.read_structure_field(
            ctx_addr, 'struct kgsl_context', 'id'))

        proc_priv_offset = dump.field_offset('struct kgsl_context',
                                             'proc_priv')
        proc_priv = dump.read_pointer(ctx_addr + proc_priv_offset)
        pid = str(dump.read_structure_field(
            proc_priv, 'struct kgsl_process_private', 'pid'))

        comm_offset = dump.field_offset('struct kgsl_process_private',
                                        'comm')
        comm = str(dump.read_cstring(proc_priv + comm_offset))
        ptr = strhex(ctx_addr)
        format_str = '{0:20} {1:20} {2:20} {3:30}'
        self.writeln(format_str.format(context_id, str(pid), comm, ptr))

    def parse_context_data(self, dump):
        format_str = '{0:20} {1:20} {2:20} {3:30}'
        self.writeln(format_str.format("CONTEXT ID", "PID", "PROCESS_NAME",
                                       "ADRENO_DRAW_CONTEXT_PTR"))
        context_idr = dump.read('device_3d0.dev.context_idr')
        self.rtw.walk_radix_tree(context_idr, self.print_context_data)

    def parse_open_process_mementry(self, dump):
        self.writeln('WARNING: Some nodes can be corrupted one, Ignore them.')
        format_str = '{0:20} {1:20} {2:20} {3:30} {4:20} {5:20}'
        print_str = format_str.format("PID", "PNAME", "INDEX", "MEMENTRY_NODE",
                                      "MEMDESC_SIZE", "GPUADDR")
        self.writeln(print_str)

        node_addr = dump.read('kgsl_driver.process_list.next')
        list_elem_offset = dump.field_offset(
            'struct kgsl_process_private', 'list')
        open_process_list_walker = linux_list.ListWalker(
            dump, node_addr, list_elem_offset)
        open_process_list_walker.walk(
            node_addr, self.__walk_process_mementry, dump, format_str)

    def __walk_process_mementry(self, kgsl_private_base_addr, dump,
                              format_string):
        pid = dump.read_structure_field(kgsl_private_base_addr,
                                        'struct kgsl_process_private', 'pid')

        comm_offset = dump.field_offset('struct kgsl_process_private', 'comm')
        pname = str(dump.read_cstring(kgsl_private_base_addr + comm_offset))

        mem_idr_offset = dump.field_offset('struct kgsl_process_private',
                                           'mem_idr')
        mementry_rt = kgsl_private_base_addr + mem_idr_offset

        try:
            self.rtw.walk_radix_tree(mementry_rt, self.__print_mementry_info,
                                     pid, pname, [True])
        except Exception:
            self.writeln("Ramdump has a corrupted mementry: pid: " + str(pid) +
                         " comm: " + pname)

    def __print_mementry_info(self, mementry_addr, pid, pname, print_header):
        dump = self.ramdump
        format_string = '{0:20} {1:20} {2:20} {3:30} {4:20} {5:20}'
        memdesc_offset = dump.field_offset('struct kgsl_mem_entry', 'memdesc')
        kgsl_memdesc_address = mementry_addr + memdesc_offset

        size = dump.read_structure_field(kgsl_memdesc_address,
                                         'struct kgsl_memdesc', 'size')
        gpuaddr = dump.read_structure_field(kgsl_memdesc_address,
                                            'struct kgsl_memdesc',
                                            'gpuaddr')
        idr_id = dump.read_structure_field(mementry_addr,
                                           'struct kgsl_mem_entry', 'id')

        if print_header[0] == True:
            self.writeln(format_string.format(str(pid), pname, hex(idr_id),
                                         hex(kgsl_memdesc_address),
                                         str(size), hex(gpuaddr)))
            # Set to False to skip printing pid and pname for the rest
            print_header[0] = False
        else:
            self.writeln(format_string.format("", "", hex(idr_id),
                                         hex(kgsl_memdesc_address),
                                         str(size), hex(gpuaddr)))

    def parse_kgsl_data(self, dump):
        open_count = dump.read('device_3d0.dev.open_count')
        state = dump.read('device_3d0.dev.state')
        requested_state = dump.read('device_3d0.dev.requested_state')
        reg_phys = dump.read('device_3d0.dev.reg_phys')
        reg_virt = dump.read('device_3d0.dev.reg_virt')
        ft_policy = dump.read('device_3d0.ft_policy')
        long_ib_detect = dump.read('device_3d0.long_ib_detect')
        pwrctrl_flag = dump.read('device_3d0.pwrctrl_flag')
        speed_bin = dump.read('device_3d0.speed_bin')
        cur_rb = dump.read('device_3d0.cur_rb')
        next_rb = dump.read('device_3d0.next_rb')
        prev_rb = dump.read('device_3d0.prev_rb')
        cur_rb_id = dump.read_structure_field(cur_rb,
                                              'struct adreno_ringbuffer', 'id')
        next_rb_id = dump.read_structure_field(next_rb,
                                              'struct adreno_ringbuffer', 'id')
        prev_rb_id = dump.read_structure_field(prev_rb,
                                              'struct adreno_ringbuffer', 'id')

        self.writeln('open_count: ' + str(open_count))
        self.writeln('state: ' + str(state))
        self.writeln('requested_state: ' + str(requested_state))
        self.writeln('reg_phys: ' + strhex(reg_phys))
        self.writeln('reg_virt: ' + strhex(reg_virt))
        self.writeln('ft_policy: ' + str(ft_policy))
        self.writeln('long_ib_detect: ' + str(long_ib_detect))
        self.writeln('pwrctrl_flag: ' + strhex(pwrctrl_flag))
        self.writeln('speed_bin: ' + str(speed_bin))
        self.writeln('cur_rb: ' + strhex(cur_rb))
        self.writeln('cur_rb_id: ' + str(cur_rb_id))
        self.writeln('next_rb: ' + strhex(next_rb))
        self.writeln('next_rb_id: ' + str(next_rb_id))
        self.writeln('prev_rb_ptr: ' + strhex(prev_rb))
        self.writeln('prev_rb_id: ' + str(prev_rb_id))

    def parse_kgsl_data_54(self, dump):
        open_count = dump.read('device_3d0.dev.open_count')
        state = dump.read('device_3d0.dev.state')
        requested_state = dump.read('device_3d0.dev.requested_state')
        reg_phys = dump.read('device_3d0.dev.reg_phys')
        reg_virt = dump.read('device_3d0.dev.reg_virt')
        ft_policy = dump.read('device_3d0.ft_policy')
        long_ib_detect = dump.read('device_3d0.long_ib_detect')
        lm_enabled = dump.read_bool('device_3d0.lm_enabled')
        acd_enabled = dump.read_bool('device_3d0.acd_enabled')
        hwcg_enabled = dump.read_bool('device_3d0.hwcg_enabled')
        throttling_enabled = dump.read_bool('device_3d0.throttling_enabled')
        sptp_pc_enabled = dump.read_bool('device_3d0.sptp_pc_enabled')
        bcl_enabled = dump.read_bool('device_3d0.bcl_enabled')
        speed_bin = dump.read('device_3d0.speed_bin')
        cur_rb = dump.read('device_3d0.cur_rb')
        next_rb = dump.read('device_3d0.next_rb')
        prev_rb = dump.read('device_3d0.prev_rb')
        cur_rb_id = dump.read_structure_field(cur_rb,
                                              'struct adreno_ringbuffer', 'id')
        next_rb_id = dump.read_structure_field(next_rb,
                                               'struct adreno_ringbuffer',
                                               'id')
        prev_rb_id = dump.read_structure_field(prev_rb,
                                               'struct adreno_ringbuffer',
                                               'id')

        self.writeln('open_count: ' + str(open_count))
        self.writeln('state: ' + str(state))
        self.writeln('requested_state: ' + str(requested_state))
        self.writeln('reg_phys: ' + strhex(reg_phys))
        self.writeln('reg_virt: ' + strhex(reg_virt))
        self.writeln('ft_policy: ' + str(ft_policy))
        self.writeln('long_ib_detect: ' + str(long_ib_detect))
        self.writeln('lm_enabled: ' + str(lm_enabled))
        self.writeln('acd_enabled: ' + str(acd_enabled))
        self.writeln('hwcg_enabled: ' + str(hwcg_enabled))
        self.writeln('throttling_enabled: ' + str(throttling_enabled))
        self.writeln('sptp_pc_enabled: ' + str(sptp_pc_enabled))
        self.writeln('bcl_enabled: ' + str(bcl_enabled))
        self.writeln('speed_bin: ' + str(speed_bin))
        self.writeln('cur_rb: ' + strhex(cur_rb))
        self.writeln('cur_rb_id: ' + str(cur_rb_id))
        self.writeln('next_rb: ' + strhex(next_rb))
        self.writeln('next_rb_id: ' + str(next_rb_id))
        self.writeln('prev_rb_ptr: ' + strhex(prev_rb))
        self.writeln('prev_rb_id: ' + str(prev_rb_id))

    def parse_kgsl_mem(self, dump):
        page_alloc = dump.read('kgsl_driver.stats.page_alloc')
        coherent = dump.read('kgsl_driver.stats.coherent')
        secure = dump.read('kgsl_driver.stats.secure')

        self.writeln('KGSL Total: ' + str_convert_to_kb(secure +
                     page_alloc + coherent))
        self.writeln('\tsecure: ' + str_convert_to_kb(secure))
        self.writeln('\tnon-secure: ' + str_convert_to_kb(page_alloc +
                     coherent))
        self.writeln('\t\tpage_alloc: ' + str_convert_to_kb(page_alloc))
        self.writeln('\t\tcoherent: ' + str_convert_to_kb(coherent))

        pools_base_addr = dump.address_of('kgsl_pools')
        shift = dump.sizeof('struct kgsl_page_pool')
        pool_order = []
        pool_size = []
        order_offset = dump.field_offset('struct kgsl_page_pool', 'pool_order')
        page_count_offset = dump.field_offset('struct kgsl_page_pool',
                                              'page_count')
        for i in range(KGSL_MAX_POOLS):
            p_order = dump.read_int(pools_base_addr + order_offset)
            pool_order.append(p_order)
            page_count = dump.read_int(pools_base_addr + page_count_offset)

            pool_size.append(page_count * (1 << p_order))
            pools_base_addr += shift

        self.writeln('\nKGSL Pool Size: ' +
                     str_convert_to_kb(sum(pool_size)*PAGE_SIZE))
        for i in range(KGSL_MAX_POOLS):
            self.writeln('\t' + str(pool_order[i]) + ' order pool size: ' +
                         str_convert_to_kb(pool_size[i]*PAGE_SIZE))

        # global_pt_entries isn't there in 5.4
        global_pt_entry_addr = dump.address_of('global_pt_entries')
        shift = dump.sizeof('struct global_pt_entry')
        MAX_GLOBAL_PT_ENTRIES = 32
        memdesc_offset = dump.field_offset('struct global_pt_entry', 'memdesc')
        total_global_size = 0
        global_secure_size = dump.read_int('secure_global_size')
        for i in range(MAX_GLOBAL_PT_ENTRIES):
            memdesc_addr = dump.read_pointer(global_pt_entry_addr +
                                             memdesc_offset)
            mem_size = dump.read_structure_field(memdesc_addr,
                                                 'struct kgsl_memdesc', 'size')
            total_global_size += mem_size
            global_pt_entry_addr += shift
        self.writeln('\nglobal_pt_entries')
        self.writeln('\tsecure: ' +
                     str_convert_to_kb(global_secure_size))
        self.writeln('\tnon-secure: ' +
                     str_convert_to_kb(total_global_size))

    def parse_kgsl_mem_54(self, dump):
        page_alloc = dump.read('kgsl_driver.stats.page_alloc')
        coherent = dump.read('kgsl_driver.stats.coherent')
        secure = dump.read('kgsl_driver.stats.secure')

        self.writeln('KGSL Total: ' + str_convert_to_kb(secure +
                     page_alloc + coherent))
        self.writeln('\tsecure: ' + str_convert_to_kb(secure))
        self.writeln('\tnon-secure: ' + str_convert_to_kb(page_alloc +
                     coherent))
        self.writeln('\t\tpage_alloc: ' + str_convert_to_kb(page_alloc))
        self.writeln('\t\tcoherent: ' + str_convert_to_kb(coherent))

        pools_base_addr = dump.address_of('kgsl_pools')
        shift = dump.sizeof('struct kgsl_page_pool')
        pool_order = []
        pool_size = []
        order_offset = dump.field_offset('struct kgsl_page_pool', 'pool_order')
        page_count_offset = dump.field_offset('struct kgsl_page_pool',
                                              'page_count')
        for i in range(KGSL_MAX_POOLS):
            p_order = dump.read_int(pools_base_addr + order_offset)
            pool_order.append(p_order)
            page_count = dump.read_int(pools_base_addr + page_count_offset)

            pool_size.append(page_count * (1 << p_order))
            pools_base_addr += shift

        self.writeln('\nKGSL Pool Size: ' +
                     str_convert_to_kb(sum(pool_size)*PAGE_SIZE))
        for i in range(KGSL_MAX_POOLS):
            self.writeln('\t' + str(pool_order[i]) + ' order pool size: ' +
                         str_convert_to_kb(pool_size[i]*PAGE_SIZE))

    def parse_dispatcher_data(self, dump):
        inflight = dump.read('device_3d0.dispatcher.inflight')
        pending_address = dump.read('device_3d0.dispatcher.pending')
        fault_counter = dump.read('device_3d0.dispatcher.fault')

        self.writeln('inflight: ' + str(inflight))
        self.writeln('pending address: '
                     + strhex(pending_address))
        self.writeln('fault_counter: ' + str(fault_counter))

    def parse_dispatcher_data_54(self, dump):
        inflight = dump.read('device_3d0.dispatcher.inflight')
        self.writeln('inflight: ' + str(inflight))

        jobs_base_addr = dump.address_of('device_3d0.dispatcher.jobs')
        shift = dump.sizeof('struct llist_head')
        self.write('jobs: ')
        active_jobs = False
        for i in range(16):
            first = dump.read_structure_field(jobs_base_addr,
                                              'struct llist_head', 'first')
            if first != 0:
                if not active_jobs:
                    self.writeln('')
                self.writeln('\tjobs[' + str(i) + '].first: ' + strhex(first))
                active_jobs = True

            jobs_base_addr += shift
        if not active_jobs:
            self.writeln('0x0')
        fault_counter = dump.read('device_3d0.dispatcher.fault')
        self.writeln('fault_counter: ' + str(fault_counter))

    def parse_rb_inflight_data(self, dump):
        ringbuffers_base_address = dump.read('device_3d0.ringbuffers')
        ringbuffers = []
        inflight_queue_result = []

        for i in range(0, KGSL_PRIORITY_MAX_RB_LEVELS):
            ringbuffers_temp = []
            rb_array_index_addr = dump.array_index(
                ringbuffers_base_address, "struct adreno_ringbuffer", i)
            wptr = dump.read_structure_field(rb_array_index_addr,
                                             'struct adreno_ringbuffer',
                                             'wptr')
            _wptr = dump.read_structure_field(rb_array_index_addr,
                                              'struct adreno_ringbuffer',
                                              '_wptr')
            last_wptr = dump.read_structure_field(
                        rb_array_index_addr,
                        'struct adreno_ringbuffer', 'last_wptr')
            id = dump.read_structure_field(rb_array_index_addr,
                                           'struct adreno_ringbuffer', 'id')
            flags = dump.read_structure_field(rb_array_index_addr,
                                              'struct adreno_ringbuffer',
                                              'flags')

            drawctxt_active = dump.read_structure_field(
                rb_array_index_addr, 'struct adreno_ringbuffer',
                'drawctxt_active')

            if drawctxt_active != 0:
                kgsl_context_id = dump.read_structure_field(
                    drawctxt_active, 'struct kgsl_context', 'id')
                proc_priv_val = dump.read_structure_field(
                    drawctxt_active, 'struct kgsl_context', 'proc_priv')
                if proc_priv_val != 0:
                    comm_offset = dump.field_offset(
                        'struct kgsl_process_private', 'comm')
                    process_name = dump.read_cstring(proc_priv_val
                                                     + comm_offset)
                else:
                    process_name = "NULL"
            else:
                kgsl_context_id = "NULL"
                process_name = "NULL"

            dispatch_q_address = rb_array_index_addr + \
                dump.field_offset('struct adreno_ringbuffer', 'dispatch_q')
            inflight = dump.read_structure_field(
                dispatch_q_address, 'struct adreno_dispatcher_drawqueue',
                'inflight')
            cmd_q_address = dispatch_q_address + dump.field_offset(
                'struct adreno_dispatcher_drawqueue', 'cmd_q')
            head = dump.read_structure_field(
                dispatch_q_address, 'struct adreno_dispatcher_drawqueue',
                'head')
            tail = dump.read_structure_field(
                dispatch_q_address, 'struct adreno_dispatcher_drawqueue',
                'tail')

            dispatcher_result = []
            while head is not tail:
                dispatcher_temp = []
                inflight_queue_index_address = dump.array_index(
                    cmd_q_address, 'struct kgsl_drawobj_cmd *', head)
                inflight_queue_index_value = dump.read_word(
                    inflight_queue_index_address)

                if inflight_queue_index_value != 0:
                    global_ts = dump.read_structure_field(
                        inflight_queue_index_value,
                        'struct kgsl_drawobj_cmd', 'global_ts')
                    fault_policy = dump.read_structure_field(
                        inflight_queue_index_value,
                        'struct kgsl_drawobj_cmd', 'fault_policy')
                    fault_recovery = dump.read_structure_field(
                        inflight_queue_index_value,
                        'struct kgsl_drawobj_cmd', 'fault_recovery')

                    base_address = inflight_queue_index_value + \
                        dump.field_offset('struct kgsl_drawobj_cmd', 'base')
                    drawobj_type = dump.read_structure_field(
                        base_address, 'struct kgsl_drawobj', 'type')
                    timestamp = dump.read_structure_field(
                        base_address, 'struct kgsl_drawobj', 'timestamp')
                    flags = dump.read_structure_field(
                        base_address, 'struct kgsl_drawobj', 'flags')
                    context_pointer = dump.read_pointer(dump.field_offset(
                        'struct kgsl_drawobj', 'context')+base_address)
                    context_id = dump.read_structure_field(
                        context_pointer, 'struct kgsl_context', 'id')
                    proc_priv = dump.read_structure_field(
                        context_pointer, 'struct kgsl_context', 'proc_priv')
                    pid = dump.read_structure_field(
                        proc_priv, 'struct kgsl_process_private', 'pid')
                else:
                    global_ts = 'NULL'
                    fault_policy = 'NULL'
                    fault_recovery = 'NULL'
                    drawobj_type = 'NULL'
                    timestamp = 'NULL'
                    flags = 'NULL'
                    context_id = 'NULL'
                    pid = 'NULL'

                dispatcher_temp.extend([i, global_ts, fault_policy,
                                        fault_recovery, drawobj_type,
                                        timestamp, flags, context_id, pid])

                dispatcher_result.append(dispatcher_temp)
                head = (head + 1) % ADRENO_DISPATCH_DRAWQUEUE_SIZE

            inflight_queue_result.append(dispatcher_result)

            ringbuffers_temp.append(rb_array_index_addr)
            ringbuffers_temp.append(wptr)
            ringbuffers_temp.append(_wptr)
            ringbuffers_temp.append(last_wptr)
            ringbuffers_temp.append(id)
            ringbuffers_temp.append(flags)
            ringbuffers_temp.append(kgsl_context_id)
            ringbuffers_temp.append(process_name)
            ringbuffers_temp.append(inflight)
            ringbuffers.append(ringbuffers_temp)

        format_str = "{0:20} {1:20} {2:20} {3:20} " \
            "{4:20} {5:20} {6:20} {7:20} {8:20}"

        print_str = format_str.format('INDEX', 'WPTR', '_WPTR', 'LAST_WPTR',
                                      'ID', 'FLAGS', 'KGSL_CONTEXT_ID',
                                      'PROCESS_NAME', 'INFLIGHT')
        self.writeln(print_str)

        index = 0
        for rb in ringbuffers:
            print_str = format_str.format(str(index), str(rb[1]), str(rb[2]),
                                          str(rb[3]), str(rb[4]), str(rb[5]),
                                          str(rb[6]), str(rb[7]), str(rb[8]))
            self.writeln(print_str)
            index = index + 1

        self.writeln()
        self.writeln("Inflight Queues:")

        format_str = "{0:20} {1:20} {2:20} {3:20} {4:20} " \
            "{5:20} {6:20} {7:20} {8:20}"

        print_str = format_str.format("ringbuffer", "global_ts",
                                      "fault_policy", "fault_recovery",
                                      "type", "timestamp", "flags",
                                      "context_id", "pid")
        self.writeln(print_str)

        # Flatten the 3D list to 1D list
        queues = sum(inflight_queue_result, [])
        for queue in queues:
            # Skip if all the entries excluding rb of the queue are empty
            if all([i == 'NULL' for i in queue[1:]]):
                pass

            self.writeln(format_str.format(str(queue[0]), str(queue[1]),
                                           str(queue[2]), str(queue[3]),
                                           str(queue[4]), str(queue[5]),
                                           str(queue[6]), str(queue[7]),
                                           str(queue[8])))

    def parse_pwrctrl_data(self, dump):
        pwrctrl_address = dump.read('device_3d0.dev.pwrctrl')
        active_pwrlevel = dump.read('device_3d0.dev.pwrctrl.active_pwrlevel')
        prev_pwrlevel = dump.read('device_3d0.dev.pwrctrl.previous_pwrlevel')
        power_flags = dump.read('device_3d0.dev.pwrctrl.power_flags')
        ctrl_flags = dump.read('device_3d0.dev.pwrctrl.ctrl_flags')
        min_pwrlevel = dump.read('device_3d0.dev.pwrctrl.min_pwrlevel')
        max_pwrlevel = dump.read('device_3d0.dev.pwrctrl.max_pwrlevel')
        bus_percent_ab = dump.read('device_3d0.dev.pwrctrl.bus_percent_ab')
        bus_width = dump.read('device_3d0.dev.pwrctrl.bus_width')
        bus_ab_mbytes = dump.read('device_3d0.dev.pwrctrl.bus_ab_mbytes')
        pwr_levels_result = []
        pwrlevels_base_address = pwrctrl_address + \
            dump.field_offset('struct kgsl_pwrctrl', 'pwrlevels')

        for i in range(0, KGSL_MAX_PWRLEVELS):
            pwr_levels_temp = []
            pwrlevels_array_idx_addr = dump.array_index(
                pwrlevels_base_address, "struct kgsl_pwrlevel", i)
            gpu_freq = dump.read_structure_field(
                pwrlevels_array_idx_addr, 'struct kgsl_pwrlevel', 'gpu_freq')
            bus_freq = dump.read_structure_field(
                pwrlevels_array_idx_addr, 'struct kgsl_pwrlevel', 'bus_freq')
            bus_min = dump.read_structure_field(
                pwrlevels_array_idx_addr, 'struct kgsl_pwrlevel', 'bus_min')
            bus_max = dump.read_structure_field(
                pwrlevels_array_idx_addr, 'struct kgsl_pwrlevel', 'bus_max')
            pwr_levels_temp.append(pwrlevels_array_idx_addr)
            pwr_levels_temp.append(gpu_freq)
            pwr_levels_temp.append(bus_freq)
            pwr_levels_temp.append(bus_min)
            pwr_levels_temp.append(bus_max)
            pwr_levels_result.append(pwr_levels_temp)

        self.writeln('pwrctrl_address:  ' + strhex(pwrctrl_address))
        self.writeln('active_pwrlevel:  ' + str(active_pwrlevel))
        self.writeln('previous_pwrlevel:  ' + str(prev_pwrlevel))
        self.writeln('power_flags:  ' + strhex(power_flags))
        self.writeln('ctrl_flags:  ' + strhex(ctrl_flags))
        self.writeln('min_pwrlevel:  ' + str(min_pwrlevel))
        self.writeln('max_pwrlevel:  ' + str(max_pwrlevel))
        self.writeln('bus_percent_ab:  ' + str(bus_percent_ab))
        self.writeln('bus_width:  ' + str(bus_width))
        self.writeln('bus_ab_mbytes:  ' + str(bus_ab_mbytes))
        self.writeln()

        self.writeln('pwrlevels_base_address:  '
                     + strhex(pwrlevels_base_address))
        format_str = '{0:<20} {1:<20} {2:<20} {3:<20} {4:<20}'
        self.writeln(format_str.format("INDEX", "GPU_FREQ",
                                       "BUS_FREQ", "BUS_MIN", "BUS_MAX"))

        index = 0
        for powerlevel in pwr_levels_result:
            print_str = format_str.format(index, powerlevel[1], powerlevel[2],
                                          powerlevel[3], powerlevel[4])
            self.writeln(print_str)
            index = index + 1

    def parse_mutex_data(self, dump):
        self.writeln("device_mutex:")
        device_mutex = dump.read('device_3d0.dev.mutex')
        mutex_val = dump.read_word(device_mutex)

        if mutex_val:
            tgid = dump.read_structure_field(
                mutex_val, 'struct task_struct', 'tgid')
            comm_add = mutex_val + \
                dump.field_offset('struct task_struct', 'comm')
            comm_val = dump.read_cstring(comm_add)
            self.writeln("tgid: " + str(tgid))
            self.writeln("comm: " + comm_val)
        else:
            self.writeln("UNLOCKED")

        self.writeln()
        self.writeln("dispatcher_mutex:")
        dispatcher_mutex = dump.read('device_3d0.dispatcher')
        dispatcher_mutex_val = dump.read_word(dispatcher_mutex)

        if dispatcher_mutex_val:
            tgid = dump.read_structure_field(
                dispatcher_mutex_val, 'struct task_struct', 'tgid')
            comm_add = dispatcher_mutex_val + \
                dump.field_offset('struct task_struct', 'comm')
            comm_val = dump.read_cstring(comm_add)
            self.writeln("tgid: " + str(tgid))
            self.writeln("comm: " + str(comm_val))
        else:
            self.writeln("UNLOCKED")

    def parse_scratch_memory(self, dump):
        hostptr = dump.read('device_3d0.dev.scratch.hostptr')
        self.writeln("hostptr:  " + strhex(hostptr))

        def add_increment(x): return x + 4

        format_str = '{0:20} {1:20} {2:20}'
        self.writeln(format_str.format("Ringbuffer_id", "RPTR_Value",
                                       "CTXT_RESTORE_ADD"))

        rptr_0 = dump.read_s32(hostptr)
        hostptr = add_increment(hostptr)
        rptr_1 = dump.read_s32(hostptr)
        hostptr = add_increment(hostptr)
        rptr_2 = dump.read_s32(hostptr)
        hostptr = add_increment(hostptr)
        rptr_3 = dump.read_s32(hostptr)
        hostptr = add_increment(hostptr)
        ctxt_0 = dump.read_s32(hostptr)
        hostptr = add_increment(hostptr)
        ctxt_1 = dump.read_s32(hostptr)
        hostptr = add_increment(hostptr)
        ctxt_2 = dump.read_s32(hostptr)
        hostptr = add_increment(hostptr)
        ctxt_3 = dump.read_s32(hostptr)

        self.writeln(format_str.format(str(0), str(rptr_0), strhex(ctxt_0)))
        self.writeln(format_str.format(str(1), str(rptr_1), strhex(ctxt_1)))
        self.writeln(format_str.format(str(2), str(rptr_2), strhex(ctxt_2)))
        self.writeln(format_str.format(str(3), str(rptr_3), strhex(ctxt_3)))

    def parse_scratch_memory_54(self, dump):
        scratch_obj = dump.read_pointer('device_3d0.dev.scratch')
        hostptr = dump.read_structure_field(scratch_obj, 'struct kgsl_memdesc',
                                            'hostptr')
        self.write("hostptr:  " + strhex(hostptr) + "\n")

        def add_increment(x): return x + 4

        format_str = '{0:20} {1:20} {2:20}'
        self.writeln(format_str.format("Ringbuffer_id", "RPTR_Value",
                                       "CTXT_RESTORE_ADD"))

        rptr_0 = dump.read_s32(hostptr)
        hostptr = add_increment(hostptr)
        rptr_1 = dump.read_s32(hostptr)
        hostptr = add_increment(hostptr)
        rptr_2 = dump.read_s32(hostptr)
        hostptr = add_increment(hostptr)
        rptr_3 = dump.read_s32(hostptr)
        hostptr = add_increment(hostptr)
        ctxt_0 = dump.read_s32(hostptr)
        hostptr = add_increment(hostptr)
        ctxt_1 = dump.read_s32(hostptr)
        hostptr = add_increment(hostptr)
        ctxt_2 = dump.read_s32(hostptr)
        hostptr = add_increment(hostptr)
        ctxt_3 = dump.read_s32(hostptr)

        self.writeln(format_str.format(str(0), str(rptr_0), strhex(ctxt_0)))
        self.writeln(format_str.format(str(1), str(rptr_1), strhex(ctxt_1)))
        self.writeln(format_str.format(str(2), str(rptr_2), strhex(ctxt_2)))
        self.writeln(format_str.format(str(3), str(rptr_3), strhex(ctxt_3)))

    def parse_memstore_memory(self, dump):
        hostptr = dump.read('device_3d0.dev.memstore.hostptr')
        self.write("hostptr:  " + strhex(hostptr) + "\n")

        def add_increment(x): return x + 4

        format_str = '{0:^20} {1:^20} {2:^20} {3:^20} {4:^20}'
        print_str = format_str.format("soptimestamp", "eoptimestamp",
                                      "preempted", "ref_wait_ts",
                                      "current_context")
        self.writeln(print_str)

        hostptr_init = hostptr
        while (hostptr - hostptr_init) <= 8*1024:
            soptimestamp = dump.read_s32(hostptr)
            hostptr = add_increment(hostptr)
            # skip unused entry
            hostptr = add_increment(hostptr)
            eoptimestamp = dump.read_s32(hostptr)
            hostptr = add_increment(hostptr)
            # skip unused entry
            hostptr = add_increment(hostptr)
            preempted = dump.read_s32(hostptr)
            hostptr = add_increment(hostptr)
            # skip unused entry
            hostptr = add_increment(hostptr)
            ref_wait_ts = dump.read_s32(hostptr)
            hostptr = add_increment(hostptr)
            # skip unused entry
            hostptr = add_increment(hostptr)
            current_context = dump.read_s32(hostptr)
            hostptr = add_increment(hostptr)
            # skip unused entry
            hostptr = add_increment(hostptr)

            if (soptimestamp or eoptimestamp or preempted or ref_wait_ts
                    or current_context):
                print_str = format_str.format(hex(soptimestamp),
                                              hex(eoptimestamp), preempted,
                                              hex(ref_wait_ts),
                                              current_context)
                self.writeln(print_str)

    def parse_memstore_memory_54(self, dump):
        memstore_obj = dump.read_pointer('device_3d0.dev.memstore')
        hostptr = dump.read_structure_field(memstore_obj,
                                            'struct kgsl_memdesc', 'hostptr')
        self.write("hostptr:  " + strhex(hostptr) + "\n")

        def add_increment(x): return x + 4

        format_str = '{0:^20} {1:^20} {2:^20} {3:^20} {4:^20}'
        print_str = format_str.format("soptimestamp", "eoptimestamp",
                                      "preempted", "ref_wait_ts",
                                      "current_context")
        self.writeln(print_str)

        hostptr_init = hostptr
        while (hostptr - hostptr_init) <= 8*1024:
            soptimestamp = dump.read_s32(hostptr)
            hostptr = add_increment(hostptr)
            # skip unused entry
            hostptr = add_increment(hostptr)
            eoptimestamp = dump.read_s32(hostptr)
            hostptr = add_increment(hostptr)
            # skip unused entry
            hostptr = add_increment(hostptr)
            preempted = dump.read_s32(hostptr)
            hostptr = add_increment(hostptr)
            # skip unused entry
            hostptr = add_increment(hostptr)
            ref_wait_ts = dump.read_s32(hostptr)
            hostptr = add_increment(hostptr)
            # skip unused entry
            hostptr = add_increment(hostptr)
            current_context = dump.read_s32(hostptr)
            hostptr = add_increment(hostptr)
            # skip unused entry
            hostptr = add_increment(hostptr)

            if (soptimestamp or eoptimestamp or preempted or ref_wait_ts
                    or current_context):
                print_str = format_str.format(hex(soptimestamp),
                                              hex(eoptimestamp), preempted,
                                              hex(ref_wait_ts),
                                              current_context)
                self.writeln(print_str)

    def parse_fence_data(self, dump):
        context_idr = dump.read('device_3d0.dev.context_idr')
        self.rtw.walk_radix_tree(context_idr, self.__print_fence_info)
        return

    def __print_fence_info(self, context_addr):
        dump = self.ramdump
        context_id = dump.read_structure_field(context_addr,
                                               'struct kgsl_context', 'id')
        ktimeline_offset = dump.field_offset('struct kgsl_context',
                                             'ktimeline')
        ktimeline_addr = dump.read_pointer(context_addr + ktimeline_offset)

        name_offset = dump.field_offset('struct kgsl_sync_timeline',
                                        'name')
        name_addr = ktimeline_addr + name_offset
        kgsl_sync_timeline_name = dump.read_cstring(name_addr)

        kgsl_sync_timeline_last_ts = dump.read_structure_field(
            ktimeline_addr, 'struct kgsl_sync_timeline',
            'last_timestamp')
        kgsl_sync_timeline_kref_counter = dump.read_byte(
            ktimeline_addr)

        self.writeln("context id: " + str(context_id))
        self.writeln("\t" + "kgsl_sync_timeline_name: "
                     + str(kgsl_sync_timeline_name))
        self.writeln("\t" + "kgsl_sync_timeline_last_timestamp: "
                     + str(kgsl_sync_timeline_last_ts))
        self.writeln("\t" + "kgsl_sync_timeline_kref_counter: "
                     + str(kgsl_sync_timeline_kref_counter))

    def parse_open_process_data(self, dump):
        format_str = '{0:10} {1:20} {2:20} {3:30} {4:20}'
        self.writeln(format_str.format("PID", "PNAME", "PROCESS_PRIVATE_PTR",
                                       "kgsl-pagetable-address",
                                       "kgsl-cur-memory"))

        node_addr = dump.read('kgsl_driver.process_list.next')
        list_elem_offset = dump.field_offset(
                            'struct kgsl_process_private', 'list')
        open_process_list_walker = linux_list.ListWalker(
                                    dump, node_addr, list_elem_offset)
        open_process_list_walker.walk(node_addr, self.walk_process_private,
                                      dump, format_str)

    def walk_process_private(self, kgsl_private_base_addr, dump, format_str):
        pid = dump.read_structure_field(
            kgsl_private_base_addr, 'struct kgsl_process_private', 'pid')

        comm_offset = dump.field_offset('struct kgsl_process_private', 'comm')
        pname = dump.read_cstring(kgsl_private_base_addr + comm_offset)

        kgsl_pagetable_address = dump.read_structure_field(
            kgsl_private_base_addr, 'struct kgsl_process_private', 'pagetable')

        stats_offset = dump.field_offset('struct kgsl_process_private',
                                         'stats')
        stats_addr = kgsl_private_base_addr + stats_offset

        val = dump.read_slong(stats_addr)

        self.writeln(format_str.format(
            str(pid), str(pname), hex(kgsl_private_base_addr),
            hex(kgsl_pagetable_address), str_convert_to_kb(val)))

    def parse_pagetables(self, dump):
        format_str = '{0:14} {1:16} {2:20} {3:20} {4:20}'
        self.writeln(format_str.format("PID", "pt_base", "ttbr0",
                                       "ctxidr", "attached"))

        node_addr = dump.read('kgsl_driver.pagetable_list.next')
        list_elem_offset = dump.field_offset(
                            'struct kgsl_pagetable', 'list')
        pagetable_list_walker = linux_list.ListWalker(
                                    dump, node_addr, list_elem_offset)
        pagetable_list_walker.walk(node_addr, self.walk_pagetable,
                                   dump, format_str)

    def walk_pagetable(self, kgsl_pagetable_base_addr, dump, format_str):
        pid = dump.read_structure_field(
            kgsl_pagetable_base_addr, 'struct kgsl_pagetable', 'name')
        if pid == 0 or pid == 1:
            return
        priv_offset = dump.field_offset('struct kgsl_pagetable', 'priv')

        ttbr0_mask = 0xFFFFFFFFFFFF
        kgsl_iommu_pt_base_addr = dump.read_pointer(kgsl_pagetable_base_addr +
                                                    priv_offset)
        ttbr0_val = dump.read_structure_field(
            kgsl_iommu_pt_base_addr, 'struct kgsl_iommu_pt', 'ttbr0')
        pt_base = ttbr0_val & ttbr0_mask

        context_idr_offset = dump.field_offset('struct kgsl_iommu_pt',
                                               'contextidr')
        context_idr_val = dump.read_u32(kgsl_iommu_pt_base_addr +
                                        context_idr_offset)

        attached_offset = dump.field_offset('struct kgsl_iommu_pt', 'attached')
        attached_val = dump.read_bool(kgsl_iommu_pt_base_addr +
                                      attached_offset)

        self.writeln(format_str.format(
            str(pid), strhex(pt_base), strhex(ttbr0_val),
            strhex(context_idr_val), str(attached_val)))

    def dump_gpu_snapshot(self, dump):
        devp_addr = dump.read('kgsl_driver.devp')
        snapshot_faultcount = dump.read_structure_field(devp_addr,
                                                        'struct kgsl_device',
                                                        'snapshot_faultcount')
        self.writeln(str(snapshot_faultcount) + ' snapshot fault(s) detected.')

        if snapshot_faultcount == 0:
            self.writeln('No GPU hang, skipping snapshot dumping.')
            return

        snapshot_offset = dump.field_offset('struct kgsl_device', 'snapshot')
        snapshot_memory_offset = dump.field_offset(
            'struct kgsl_device', 'snapshot_memory')
        snapshot_memory_size = dump.read_u32(devp_addr +
                                             snapshot_memory_offset + 8)
        snapshot_base_addr = dump.read_pointer(devp_addr + snapshot_offset)
        if snapshot_base_addr == 0:
            self.writeln('Snapshot not found.')
            return

        snapshot_start = dump.read_structure_field(
            snapshot_base_addr, 'struct kgsl_snapshot', 'start')
        snapshot_size = dump.read_structure_field(
            snapshot_base_addr, 'struct kgsl_snapshot', 'size')
        snapshot_timestamp = dump.read_structure_field(
            snapshot_base_addr, 'struct kgsl_snapshot', 'timestamp')
        snapshot_process_offset = dump.field_offset('struct kgsl_snapshot',
                                                    'process')
        snapshot_process = dump.read_pointer(snapshot_base_addr +
                                             snapshot_process_offset)
        snapshot_pid = dump.read_structure_field(
            snapshot_process, 'struct kgsl_process_private', 'pid')

        self.writeln('Snapshot Details:')
        self.writeln('\tStart Address: ' + strhex(snapshot_start))
        self.writeln('\tSize: ' + str(snapshot_size))
        self.writeln('\tTimestamp: ' + str(snapshot_timestamp))
        self.writeln('\tProcess PID: ' + str(snapshot_pid))

        file_name = 'gpu_snapshot_' + str(snapshot_timestamp) + '.bpmd'
        file = self.ramdump.open_file('gpu_parser/' + file_name, 'wb')

        if snapshot_size == 0:
            self.write('Snapshot freeze not completed.')
            self.writeln('Dumping entire region to gpu_snapshot.bpmd')
            data = self.ramdump.read_binarystring(snapshot_start,
                                                  snapshot_memory_size)
        else:
            self.writeln('\nDumping ' + str_convert_to_kb(snapshot_size) +
                         ' starting from ' + strhex(snapshot_start) +
                         ' to ' + file_name)
            data = self.ramdump.read_binarystring(snapshot_start,
                                                  snapshot_size)
        file.write(data)
        file.close()
