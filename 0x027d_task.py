import time
import random
import logging
logging.basicConfig(format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                    datefmt='%Y-%m-%d:%H:%M:%S')
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

def standby(self, eoj, jdsIdx):
    jsonDevSchedule = self.jsonDevScheduleList[jdsIdx]
    idx = jsonDevSchedule["schedule_idx"]
    prop = jsonDevSchedule["json"]["schedule"][idx]["property"]
    return "running"    # keep running and never complete

def operate(self, eoj, jdsIdx):
    #logger.debug("eoj:%r jdsIdx:%r" % (eoj, jdsIdx))
    jsonDevSchedule = self.jsonDevScheduleList[jdsIdx]
    idx = jsonDevSchedule["schedule_idx"]
    prop = jsonDevSchedule["json"]["schedule"][idx]["property"]
    logger.debug("prop:%r" % prop)
    logger.debug("time(%r) > next_time(%r)" % (time.time(), prop["task_next_time"]))
    if (time.time() < prop["task_next_time"]):
        return "running"
    # check remaining capacity(0xE4) >= 99%, charging done
    cap3 = int(self.get_device_eoj_the_epc(eoj, "E4"), 16)
    #logger.debug("cap3:%r" % (cap3))
    if ((prop["operation_mode"] == "Charging" and cap3 >= 99) or
        (prop["operation_mode"] == "Discharging" and cap3 <= 5)):
        # if "operation_mode_setting] != 0x46(auto) then complete 
        # and set 0xDA/0xCF as 0x44(standby)
        if (jsonDevSchedule["json"]["operation_mode_setting"]["value"] != "46"):
            value = "44"
            self.put_device_eoj_the_epc(eoj, 
                        jsonDevSchedule["json"]["operation_mode_setting"]["epc"],
                        value)
            self.put_device_eoj_the_epc(eoj, 
                        jsonDevSchedule["json"]["working_operation_status"]["epc"],
                        value)
        return "complete"
    if (prop["task_last_time"] == 0):
        prop["task_last_time"] = time.time()
        prop["task_next_time"] = time.time() + prop["duration_sec"]
        return "running"
    cap1 = int(self.get_device_eoj_the_epc(eoj, "E2"), 16)
    if (time.time() >= prop["task_next_time"]):
        chg_time_sec = time.time() - prop["task_last_time"]
        # accumulate charging capacity
        chg_Wh = 0
        if (prop["operation_mode"] == "Charging"):
            chg_W = prop["chg_Wh"]
        elif (prop["operation_mode"] == "Discharging"):
            chg_W = random.randint(prop["dsg_Wh"][0], prop["dsg_Wh"][1])
        else:
            logger.error("Unknown operation mode(%r)" % (prop["operation_mode"]))
        chg_Wh = int(chg_W * chg_time_sec * prop["duration_ratio"] / 3600)
        cap_Wh = chg_Wh + cap1
        cap_Ah = int(float(cap_Wh) / prop["voltage"] / 0.1) # unit: 0.1Ah
        cap_percent = int(cap_Wh / prop["cap_Wh"] * 100)
        #logger.debug("cap_Wh:%r cap_Ah:%r" % (cap_Wh, cap_Ah))
        cap1_hex = '{:08x}'.format(cap_Wh)
        cap2_hex = '{:04x}'.format(cap_Ah)
        cap3_hex = '{:02x}'.format(cap_percent)
        logger.debug("cap1:%r cap2:%r cap3:%r" % (cap1_hex, cap2_hex, cap3_hex))
        # update values to emulator
        self.put_device_eoj_the_epc(eoj, "E2", cap1_hex)
        self.put_device_eoj_the_epc(eoj, "E3", cap2_hex)
        self.put_device_eoj_the_epc(eoj, "E4", cap3_hex)
        if (prop["operation_mode"] == "Charging"):
            epc = "D8"
        elif (prop["operation_mode"] == "Discharging"):
             epc = "D6"
        cumu = int(int(self.get_device_eoj_the_epc(eoj, epc), 16) + abs(chg_Wh))
        cumu_hex = '{:08x}'.format(cumu)
        self.put_device_eoj_the_epc(eoj, epc, cumu_hex)
        prop["task_last_time"] = time.time()
        prop["task_next_time"] = time.time() + prop["duration_sec"]
        return "running"