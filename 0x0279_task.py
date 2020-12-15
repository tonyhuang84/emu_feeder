import time
import datetime as dt
import random
import logging
logging.basicConfig(format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                    datefmt='%Y-%m-%d:%H:%M:%S')
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

def operate(self, eoj, jdsIdx):
    jsonDevSchedule = self.jsonDevScheduleList[jdsIdx]
    idx = jsonDevSchedule["schedule_idx"]
    prop = jsonDevSchedule["json"]["schedule"][idx]["property"]
    #logger.debug("prop:%r" % prop)
    logger.debug("time(%r) > next_time(%r)" % (time.time(), prop["task_next_time"]))
    if (prop["task_last_time"] == 0):
        prop["task_last_time"] = time.time()
        prop["task_next_time"] = time.time() + prop["duration_sec"]
        return "running"
    if (time.time() < prop["task_next_time"]):
        return "running"

    ins_gen_W = 0
    hour = dt.datetime.today().hour + prop["timezone_offset"]
    logger.debug("hour:%r gen_gap:%r~%r" % (hour, prop["gen_power_period"][0], prop["gen_power_period"][1]))
    if (hour >= prop["gen_power_period"][0] and 
        hour < prop["gen_power_period"][1]):
        chg_time_sec = time.time() - prop["task_last_time"]
        ins_gen_W = random.randint(prop["ins_gen_Wh"][0], prop["ins_gen_Wh"][1])
        ins_gen_Wh = int(ins_gen_W * chg_time_sec * prop["duration_ratio"] / 3600)
        cumu_gen_Wh = int(self.get_device_eoj_the_epc(eoj, "E1"), 16) + ins_gen_Wh
        ins_sold_Wh = int(ins_gen_Wh * prop["ins_sold_Wh_percent"])
        cumu_sold = int(self.get_device_eoj_the_epc(eoj, "E3"), 16) + ins_sold_Wh
        logger.debug("ins_gen_W:%r ins_gen_Wh:%r ins_sold_Wh:%r cumu_sold:%r" % (ins_gen_W, ins_gen_Wh, ins_sold_Wh, cumu_sold))
        cumu_gen_Wh_hex = '{:08x}'.format(cumu_gen_Wh)
        cumu_sold_hex = '{:08x}'.format(cumu_sold)
        self.put_device_eoj_the_epc(eoj, "E1", cumu_gen_Wh_hex)
        self.put_device_eoj_the_epc(eoj, "E3", cumu_sold_hex)

    ins_gen_W_hex = '{:04x}'.format(ins_gen_W)
    self.put_device_eoj_the_epc(eoj, "E0", ins_gen_W_hex)
    prop["task_last_time"] = time.time()
    prop["task_next_time"] = time.time() + prop["duration_sec"]
    return "running"