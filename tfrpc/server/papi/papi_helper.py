from pypapi import events, papi_low as papi
import os
import time

papi_event_strings = {
    events.PAPI_TOT_CYC: "PAPI_TOT_CYC",
    events.PAPI_TOT_INS: "PAPI_TOT_INS",
    events.PAPI_LST_INS: "PAPI_LST_INS",

    events.PAPI_L1_ICH: "PAPI_L1_ICH",
    events.PAPI_L1_DCH: "PAPI_L1_DCH",
    events.PAPI_L1_ICM: "PAPI_L1_ICM",
    events.PAPI_L1_DCM: "PAPI_L1_DCM",
    events.PAPI_L1_ICA: "PAPI_L1_ICA",
    events.PAPI_L1_DCA: "PAPI_L1_DCA",

    events.PAPI_L2_ICH: "PAPI_L2_ICH",
    events.PAPI_L2_DCH: "PAPI_L2_DCH",
    events.PAPI_L2_ICM: "PAPI_L2_ICM",
    events.PAPI_L2_DCM: "PAPI_L2_DCM",
    events.PAPI_L2_ICA: "PAPI_L2_ICA",
    events.PAPI_L2_DCA: "PAPI_L2_DCA",

    events.PAPI_L3_ICH: "PAPI_L3_ICH",
    events.PAPI_L3_DCH: "PAPI_L3_DCH",
    events.PAPI_L3_ICM: "PAPI_L3_ICM",
    events.PAPI_L3_DCM: "PAPI_L3_DCM",
    events.PAPI_L3_ICA: "PAPI_L3_ICA",
    events.PAPI_L3_DCA: "PAPI_L3_DCA",

    events.PAPI_TLB_DM: "PAPI_TLB_DM",
    events.PAPI_TLB_IM: "PAPI_TLB_IM",
}

class pypapi_wrapper:
    """Wrapper class for python_papi"""
    event_sets = [
        [events.PAPI_TOT_CYC, events.PAPI_TOT_INS],
        [events.PAPI_L1_ICM, events.PAPI_L1_DCM],
        #[events.PAPI_MEM_WCY, events.PAPI_TOT_INS, events.PAPI_TOT_CYC, events.PAPI_LST_INS, events.PAPI_REF_CYC, events.PAPI_PRF_DM],
        [events.PAPI_L2_ICM,events.PAPI_L2_DCM,events.PAPI_L2_ICA,events.PAPI_L2_DCA] ,
        [events.PAPI_L3_TCM, events.PAPI_L3_TCA],
        [events.PAPI_TLB_DM, events.PAPI_TLB_IM],
    ]
    set_index = -1
    events=[]

    def __init__(self, set_num):
        if (set_num > len(pypapi_wrapper.event_sets) - 1):
            raise ValueError("set_num can't be creater than " + str(len(self.event_sets)-1))
        else:
            papi.library_init()
            self.set_index = set_num
            current_set = pypapi_wrapper.event_sets[self.set_index]
            self.events = papi.create_eventset()
            papi.add_events(self.events, current_set)

    def getCounters(self):
        return papi.list_events(self.events)

    def start(self):
        papi.start(self.events)

    def stop(self):
        return papi.stop(self.events)

    def read(self):
        return papi.read(self.events)

    def accum(self, values):
        return papi.accum(self.events, values)

    def cleanup(self):
        papi.cleanup_eventset(self.events)
        papi.destroy_eventset(self.events)

