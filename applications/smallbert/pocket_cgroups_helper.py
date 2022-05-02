import subprocess

class Utils:
    @staticmethod
    def get_container_id(name: str):
        container_id = subprocess.check_output(f'docker inspect --format=\'{{{{.Id}}}}\' {name}', shell=True, encoding='utf-8').replace('/','').strip()
        return container_id

    @staticmethod
    def get_max_mem_usage(id: str):
        with open(f'/sys/fs/cgroup/memory/docker/{id}/memory.max_usage_in_bytes', 'r') as f_peak_mem:
            peak_memory = f_peak_mem.read()
        return peak_memory

    @staticmethod
    def get_cpu_usage(id: str):
        with open(f'/sys/fs/cgroup/cpu/docker/{id}/cpuacct.usage', 'r') as f_cpuusage:
            cpu_usage = f_cpuusage.read()
        return cpu_usage

    @staticmethod
    def get_page_fault(id: str):
        pagefault =''
        major_pagefault = ''
        with open(f'/sys/fs/cgroup/memory/docker/{id}/memory.stat', 'r') as mem_stat:
            while True:
                line = mem_stat.readline()
                if line == '':
                    break
                if 'pgfault' in line:
                    pagefault = line.split()[1]
                elif 'pgmajfault' in line:
                    major_pagefault = line.split()[1]
        return pagefault, major_pagefault

    @staticmethod
    def remove_container(id_or_name: str):
        # process = subprocess.run(['docker', 'rm', '-f', id_or_name], check=True)
        process = subprocess.run(['docker', 'stop', '-t', '0', id_or_name], check=True)

    @staticmethod
    def stop_container(id_or_name: str):
        # process = subprocess.run(['docker', 'rm', '-f', id_or_name], check=True)
        process = subprocess.run(['docker', 'stop', '-t', '0', id_or_name], check=True)

    @staticmethod
    def kill_docker_container(container_name, signal='TERM'):
        command = ['docker', 'kill', '-s', signal, container_name]
        process = subprocess.run(command, check=True)

    @staticmethod
    def get_container_pid(container_name):
        pid = subprocess.check_output(f'docker inspect --format=\'{{{{.State.Pid}}}}\' {container_name}', shell=True, encoding='utf-8').replace('/','').strip()
        return pid

    @staticmethod
    def get_elapsed_time(container_name):
        start_str = subprocess.check_output(f'docker inspect --format=\'{{{{.State.StartedAt}}}}\' {container_name} | xargs date +%s.%N -d', shell=True, encoding='utf-8').replace('/','').strip()
        end_str = subprocess.check_output(f'docker inspect --format=\'{{{{.State.FinishedAt}}}}\' {container_name} | xargs date +%s.%N -d', shell=True, encoding='utf-8').replace('/','').strip()
        start = float(start_str)
        end = float(end_str)
        return str(end-start)

    @staticmethod
    def get_rss(container_id='self'):
        if container_id == 'self':
            with open(f'/sys/fs/cgroup/memory/memory.usage_in_bytes') as rss_f:
                rss = rss_f.read()
            return int(rss)
        else:
            with open(f'/ext/cg/memory/docker/{container_id}/memory.usage_in_bytes') as rss_f:
                rss = rss_f.read()
            return int(rss)

    @staticmethod
    def get_cpu_time(container_id='self'):
        if container_id == 'self':
            with open(f'/sys/fs/cgroup/cpu/cpuacct.usage') as cpu_f:
                cpu = cpu_f.read()
            return int(cpu)
        else:
            with open(f'/ext/cg/cpuacct/docker/{container_id}/cpuacct.usage') as cpu_f:
                cpu = cpu_f.read()
            return int(cpu)


class Profiler:
    undone = 0
    in_progress = 1
    done = 2
    def __init__(self, backend_uid):
        self.status = Profiler.undone
        self.backend_uid = backend_uid

    def start_resource_measure(self, collect_backend=False):
        self.collect_backend=collect_backend
        self.status = Profiler.in_progress
        self.start_fe_mem = Utils.get_rss('self')
        self.start_fe_cpu = Utils.get_cpu_time('self')
        if self.collect_backend:
            self.start_be_mem = Utils.get_rss(self.backend_uid)
            self.start_be_cpu = Utils.get_cpu_time(self.backend_uid)


    def stop_resource_measure(self):
        self.status = Profiler.done
        self.end_fe_mem = Utils.get_rss()
        self.end_fe_cpu = Utils.get_cpu_time('self')
        if self.collect_backend:
            self.end_be_mem= Utils.get_rss(self.backend_uid)
            self.end_be_cpu = Utils.get_cpu_time(self.backend_uid)

    def get_resource_measure(self):
        if self.status != Profiler.done:
            raise Exception('The results are not available yet!')
        fe_mem = self.end_fe_mem - self.start_fe_mem
        fe_cpu = self.end_fe_cpu - self.start_fe_cpu
        if self.collect_backend:
            be_mem = self.end_be_mem - self.start_be_mem
            be_cpu = self.end_be_cpu - self.start_be_cpu
        else:
            be_mem = None
            be_cpu = None

        return (fe_mem, fe_cpu), (be_mem, be_cpu)
        