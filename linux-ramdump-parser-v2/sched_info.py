# Copyright (c) 2019-2021, The Linux Foundation. All rights reserved.
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

DEFAULT_MIGRATION_NR=32
DEFAULT_MIGRATION_COST=500000
DEFAULT_RT_PERIOD=1000000
DEFAULT_RT_RUNTIME=950000
SCHED_CAPACITY_SHIFT=10

cpu_online_bits = 0

def mask_bitset_pos(cpumask):
    obj = [i for i in range(cpumask.bit_length()) if cpumask & (1<<i)]
    if len(obj) == 0:
        return None
    else:
        return obj

def verify_active_cpus(ramdump):
    cpu_topology_addr = ramdump.address_of('cpu_topology')
    cpu_topology_size = ramdump.sizeof('struct cpu_topology')
    cpu_isolated_bits = 0
    global cpu_online_bits

    if (ramdump.kernel_version >= (4, 19, 0)):
        cluster_id_off = ramdump.field_offset('struct cpu_topology', 'package_id')
    else:
        cluster_id_off = ramdump.field_offset('struct cpu_topology', 'cluster_id')

    nr_cpus = ramdump.get_num_cpus()

    # Skip !SMP/UP systems(with single cpu).
    if not ramdump.is_config_defined('CONFIG_SMP') or (nr_cpus <= 1):
        print ("Ramdmp is UP or !SMP or nrcpus <=1 ")
        return

    # Get online cpus from runqueue
    runqueues_addr = ramdump.address_of('runqueues')
    online_offset = ramdump.field_offset('struct rq', 'online')

    for i in ramdump.iter_cpus():
        rq_addr = runqueues_addr + ramdump.per_cpu_offset(i)
        online = ramdump.read_int(rq_addr + online_offset)
        cpu_online_bits |= (online << i)

    print("cpu_online_bits.. {0}".format(cpu_online_bits))
    if (ramdump.kernel_version >= (5, 10, 0)):
        cpu_isolated_bits = ramdump.read_word('__cpu_active_mask')
    elif (ramdump.kernel_version >= (4, 9, 0)):
        cpu_isolated_bits = ramdump.read_word('__cpu_isolated_mask')
    elif (ramdump.kernel_version >= (4, 4, 0)):
        cpu_isolated_bits = ramdump.read_word('cpu_isolated_bits')

    if (cluster_id_off is None):
        print_out_str("\n Invalid cluster topology detected\n")

    # INFO: from 4.19 onwards, core_sibling mask contains only online cpus,
    #       find out cluster cpus dynamically.

    cluster_cpus = [0]
    for j in range(0, nr_cpus):
        c_id = ramdump.read_int(cpu_topology_addr + (j * cpu_topology_size) + cluster_id_off)
        if len(cluster_cpus) <= c_id :
            cluster_cpus.extend([0])
        cluster_cpus[c_id] |= (1 << j)

    for i in range(0, len(cluster_cpus)):
        cluster_online_cpus = cpu_online_bits & cluster_cpus[i]
        cluster_nr_oncpus = bin(cluster_online_cpus).count('1')
        cluster_isolated_cpus = cpu_isolated_bits & cluster_cpus[i]
        cluster_nr_isocpus = bin(cluster_isolated_cpus).count('1')

        if (bin(cluster_cpus[i]).count('1') > 2):
            min_req_cpus = 2
        else:
            min_req_cpus = 1

        if ((cluster_nr_oncpus - cluster_nr_isocpus) < min_req_cpus):
                print_out_str("\n" + "*" * 10 + " WARNING " + "*" * 10 + "\n")
                print_out_str("\tMinimum active cpus are not available in the cluster {0}\n".format(i))

                print_out_str("*" * 10 + " WARNING " + "*" * 10 + "\n")
        print_out_str("\tCluster cpus: {0}  Online cpus: {1} Isolated cpus: {2} nr_cpu: {3}\n".format(
                        mask_bitset_pos(cluster_cpus[i]),
                        mask_bitset_pos(cluster_online_cpus),
                        mask_bitset_pos(cluster_isolated_cpus),
                        bin(cluster_cpus[i]).count('1')))

def dump_cpufreq_data(ramdump):
    cpufreq_data_addr = ramdump.address_of('cpufreq_cpu_data')
    cpuinfo_off = ramdump.field_offset('struct cpufreq_policy', 'cpuinfo')
    runqueues_addr = ramdump.address_of('runqueues')

    print_out_str("\nCPU Frequency information:\n" + "-" * 10)
    for i in ramdump.iter_cpus():
        cpu_data_addr = ramdump.read_u64(cpufreq_data_addr + ramdump.per_cpu_offset(i))
        rq_addr = runqueues_addr + ramdump.per_cpu_offset(i)

        cur_freq = ramdump.read_structure_field(cpu_data_addr, 'struct cpufreq_policy', 'cur')
        min_freq = ramdump.read_structure_field(cpu_data_addr, 'struct cpufreq_policy', 'min')
        max_freq = ramdump.read_structure_field(cpu_data_addr, 'struct cpufreq_policy', 'max')

        cpuinfo_min_freq = ramdump.read_int(cpu_data_addr + cpuinfo_off + ramdump.field_offset('struct cpufreq_cpuinfo', 'min_freq'))
        cpuinfo_max_freq = ramdump.read_int(cpu_data_addr + cpuinfo_off + ramdump.field_offset('struct cpufreq_cpuinfo', 'max_freq'))

        gov = ramdump.read_structure_field(cpu_data_addr, 'struct cpufreq_policy', 'governor')
        gov_name = ramdump.read_cstring(gov + ramdump.field_offset('struct cpufreq_governor', 'name'))

        cap_orig = ramdump.read_structure_field(rq_addr, 'struct rq', 'cpu_capacity_orig')
        curr_cap = ramdump.read_structure_field(rq_addr, 'struct rq', 'cpu_capacity')
        if (ramdump.kernel_version >= (5, 10, 0)):
            max_thermal_cap = (1 << SCHED_CAPACITY_SHIFT)
            thermal_pressure = ramdump.read_u64(ramdump.address_of('thermal_pressure') + ramdump.per_cpu_offset(i))
            thermal_cap = max_thermal_cap - thermal_pressure
        else:
            thermal_cap = ramdump.read_word(ramdump.array_index(ramdump.address_of('thermal_cap_cpu'), 'unsigned long', i))

        arch_scale = ramdump.read_int(ramdump.address_of('cpu_scale') + ramdump.per_cpu_offset(i))

        print_out_str("CPU:{0}\tGovernor:{1}\t cur_freq:{2}, max_freq:{3}, min_freq{4}  cpuinfo: min_freq:{5}, max_freq:{6}"
                    .format(i, gov_name, cur_freq, max_freq, min_freq, cpuinfo_min_freq, cpuinfo_max_freq))
        print_out_str("\tCapacity: capacity_orig:{0}, cur_cap:{1}, arch_scale:{2}\n".format(cap_orig, curr_cap, arch_scale))


@register_parser('--sched-info', 'Verify scheduler\'s various parameter status')
class Schedinfo(RamParser):
    def parse(self):
        global cpu_online_bits
        # Active cpu check verified by default!
        #verify_active_cpus(self.ramdump)

        # print cpufreq info
        dump_cpufreq_data(self.ramdump)

        # verify nr_migrates
        sched_nr_migrate = self.ramdump.read_u32('sysctl_sched_nr_migrate')
        if (sched_nr_migrate != DEFAULT_MIGRATION_NR):
            print_out_str("*" * 5 + " WARNING:" + "\n")
            print_out_str("\t sysctl_sched_nr_migrate has changed!!\n")
            print_out_str("\t If it is single digit, scheduler's load balancer has broken in the dump\n")

        # verify migration cost
        sched_migration_cost = self.ramdump.read_u32('sysctl_sched_migration_cost')
        if (sched_migration_cost != DEFAULT_MIGRATION_COST):
            print_out_str("*" * 5 + " WARNING:" + "\n")
            print_out_str("\t sysctl_sched_migration_cost has changed!!\n")
            print_out_str("\t\tDefault: 500000 and Value in dump:{0}\n".format(sched_migration_cost))

        # verify CFS BANDWIDTH enabled
        cfs_bandwidth_enabled = self.ramdump.read_u32('sysctl_sched_cfs_bandwidth_slice')
        if cfs_bandwidth_enabled is not None:
            print_out_str("*" * 5 + " INFORMATION:" + "\n")
            print_out_str("\tCFS_BANDWIDTH is enabled in the dump!!\n")
            print_out_str("\tBandwidth slice: {0}\n".format(cfs_bandwidth_enabled))

        #verify RT threasholds
        sched_rt_runtime = self.ramdump.read_u32('sysctl_sched_rt_runtime')
        sched_rt_period = self.ramdump.read_u32('sysctl_sched_rt_period')
        if (sched_rt_runtime != DEFAULT_RT_RUNTIME) or (sched_rt_period != DEFAULT_RT_PERIOD):
            print_out_str("*" * 5 + " WARNING:" + "\n")
            print_out_str("\t RT sysctl knobs may have changed!!\n")
            print_out_str("\t\t sysctl_sched_rt_runtime Default:{0} and Value in dump:{1}\n".format(DEFAULT_RT_RUNTIME, sched_rt_runtime))
            print_out_str("\t\t sysctl_sched_rt_period Default:{0} and Value in dump:{1}\n".format(DEFAULT_RT_PERIOD, sched_rt_period))

        # verify rq root domain
        runqueues_addr = self.ramdump.address_of('runqueues')
        rd_offset = self.ramdump.field_offset('struct rq', 'rd')
        sd_offset = self.ramdump.field_offset('struct rq', 'sd')
        def_rd_addr = self.ramdump.address_of('def_root_domain')
        for cpu in (mask_bitset_pos(cpu_online_bits)):
            rq_addr = runqueues_addr + self.ramdump.per_cpu_offset(cpu)
            rd = self.ramdump.read_word(rq_addr + rd_offset)
            sd = self.ramdump.read_word(rq_addr + sd_offset)
            if rd == def_rd_addr :
                print_out_str("*" * 5 + " WARNING:" + "\n")
                print_out_str("Online cpu:{0} has attached to default sched root domain {1:x}\n".format(cpu, def_rd_addr))
            if sd == 0 or sd == None:
                print_out_str("*" * 5 + " WARNING:" + "\n")
                print_out_str("Online cpu:{0} has Null sched_domain!!\n".format(cpu))
