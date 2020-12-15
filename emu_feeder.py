import requests
import json
import time
import signal
import sys
import os
import logging
logging.basicConfig(format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                    datefmt='%Y-%m-%d:%H:%M:%S')
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

'''
url = "http://172.17.0.2:8880/api/device/eojs/027901/epcs/E1"
jsonData = json.load(open("pv_0x0279.json"))
print(jsonData)
headers = {'content-type': 'application/json'}
r = requests.put(url, data=json.dumps(jsonData), headers=headers)
print(r.text)
'''

gIsTest = False

class EmuFeeder(object):
    def __init__(self):
        self._host = "http://127.0.0.1:8880"
        self.jsonDevScheduleList = [
            {
                "file": "0x027d_auto.json",
                "is_enable": False,
                "schedule_idx": 0,
                "task": None
            },
            {
                "file": "0x027d_charge.json",
                "is_enable": False,
                "schedule_idx": 0,
                "task": None
            },
            {
                "file": "0x027d_discharge.json",
                "is_enable": False,
                "schedule_idx": 0,
                "task": None
            },
            {
                "file": "0x0279.json",
                "is_enable": False,
                "schedule_idx": 0,
                "task": None
            }
        ]

    def start(self):
        cwd = os.path.dirname(os.path.realpath(__file__))
        logger.debug("start()+ cwd:%r" % (cwd))
        ret = self.get_device_power()
        if (ret):
            # load schedule json files
            for i in range(len(self.jsonDevScheduleList)):
                self.jsonDevScheduleList[i]["json"] = json.load(open(cwd + "/" + self.jsonDevScheduleList[i]["file"]))
                #logger.debug("json:%r" % self.jsonDevScheduleList[i]["json"])
                self.jsonDevScheduleList[i]["is_enable"] = self.check_device_schedue_whether_enable(self.jsonDevScheduleList[i]["json"])
                #logger.debug("i:%d is_enable:%r" % (i, self.jsonDevScheduleList[i]["is_enable"]))
        return ret

    def execute(self):
        logger.debug("execute()+")
        while (True):
            # scheduling
            for i in range(len(self.jsonDevScheduleList)):
                logger.debug("=====> i:%d" % (i))
                jds = self.jsonDevScheduleList[i]
                #logger.debug("json:%r" % (jds["json"]))
                jds["is_enable"] = self.check_device_schedue_whether_enable(jds["json"])
                logger.debug("i:%d is_enable:%r" % (i, jds["is_enable"]))
                if (jds["is_enable"]):
                    self.execute_task(i)
            time.sleep(1)

    def stop(self):
        logger.debug("stop()+")
        # TODO

    def execute_task(self, jdsIdx):
        jsonDevSchedule = self.jsonDevScheduleList[jdsIdx]
        #logger.debug("%r" % jsonDevSchedule)
        task = None
        idx = jsonDevSchedule["schedule_idx"]
        logger.debug("schedule_idx:%r" % (idx))
        schedule = jsonDevSchedule["json"]["schedule"][idx]
        if (jsonDevSchedule["task"] == None):
            task = __import__(schedule["task_proc"]["module"])
            jsonDevSchedule["task"] = task
            schedule["property"]["task_next_time"] = 0
            schedule["property"]["task_last_time"] = 0
        else:
            task = jsonDevSchedule["task"]
        eoj = jsonDevSchedule["json"]["eoj"] + jsonDevSchedule["json"]["instance_number"]
        func = "task." + schedule["task_proc"]["function"] + "(self, " + json.dumps(eoj) + ", " + str(jdsIdx) + ")"
        logger.debug("func:%s" % func)

        ret = eval(func)
        if (ret == "complete"):
            # move to next schedule
            jsonDevSchedule["schedule_idx"] = (idx + 1) % len(jsonDevSchedule["json"]["schedule"])
            logger.debug("new schedule_idx:%r" % (jsonDevSchedule["schedule_idx"]))
            jsonDevSchedule["task"] = None
        elif (ret == "running"):
            pass
        else:
            # something went wrong and disable the task
            jsonDevSchedule["is_enable"] = False

    def check_device_schedue_whether_enable(self, jsonDevSchedule):
        # check eoj whether exist or not
        if (not self.get_device_the_eoj(jsonDevSchedule["eoj"] + jsonDevSchedule["instance_number"])):
            logger.error("EOJ(%r) not found" % (jsonDevSchedule["eoj"] + jsonDevSchedule["instance_number"]))
            return False
        # check operation status
        if (not self.check_device_operation_status(jsonDevSchedule)):
            return False

        return True

    def check_device_operation_status(self, jsonDevSchedule):
        eoj = jsonDevSchedule["eoj"] + jsonDevSchedule["instance_number"]
        if (jsonDevSchedule.get("operation_mode_setting") == None):
            return True
        ret = self.get_device_eoj_the_epc(eoj, jsonDevSchedule["operation_mode_setting"]["epc"])
        if (ret == jsonDevSchedule["operation_mode_setting"]["value"]):
            # to sync the "working_operation_status" value
            ret = self.put_device_eoj_the_epc(eoj, 
                    jsonDevSchedule["working_operation_status"]["epc"],
                    jsonDevSchedule["working_operation_status"]["value"])
            if (not ret): 
                logger.error("set working_operation_status failed")
            return ret
        logger.warn("operation_mode_setting(%r) not expect value(%r)" % (ret, jsonDevSchedule["operation_mode_setting"]["value"]))
        return False

    def get_device_power(self):
        url = self._host + "/api/device/power"
        logger.debug("url:%r" % url)
        ret = json.loads(self.http_api_get(url))
        if (ret["code"] == 200 and ret["data"]["powerStatus"] == True):
            return True
        logger.error("ret:%r" % (ret))
        return False

    def get_device_the_eoj(self, eoj):
        url = self._host + "/api/device/eojs/" + eoj
        ret = json.loads(self.http_api_get(url))
        if (ret["code"] == 200):
            return True
        return False

    def get_device_eoj_the_epc(self, eoj, epc):
        url = self._host + "/api/device/eojs/" + eoj + "/epcs/" + epc
        ret = json.loads(self.http_api_get(url))
        if (ret["code"] != 200):
            return "40"     # "Other"
        return ret["data"]["elProperty"]["edt"]["hex"]

    def put_device_eoj_the_epc(self, eoj, epc, val):
        url = self._host + "/api/device/eojs/" + eoj + "/epcs/" + epc
        edt = "{\"edt\":\"%s\"}" % val
        jsonData = json.loads(edt)
        ret = json.loads(self.http_api_put(url, jsonData))
        if (ret["code"] != 200):
            return False
        return True

    def http_api_put(self, url, jsonData):
        headers = {'content-type': 'application/json'}
        r = requests.put(url, data=json.dumps(jsonData), headers=headers)
        #print("http_api_get() ret:%r" % r.text)
        return r.text
        
    def http_api_get(self, url):
        r = requests.get(url)
        #print("http_api_get() ret:%r" % r.text)
        return r.text

    def test(self):
        #self.test_get_device_description()
        self.test_get_device_power()
        #self.test_get_device_eojs()
        eoj = "027D01"
        #self.test_get_device_the_eoj(eoj)
        #self.test_get_device_eoj_epcs(eoj)
        epc = "DA"
        self.test_get_device_eoj_the_epc(eoj, epc)
        val = "00003B61"
        #self.test_put_device_eoj_the_epc(eoj, epc, val)
        epc = "E0"
        val = "0050"
        #self.test_put_device_eoj_the_epc(eoj, epc, val)

    def test_get_device_description(self):
        url = self._host + "/api/deviceDescriptions"
        self.http_api_get(url)
        
    def test_get_device_power(self):
        ret = self.get_device_power()
        print("ret:%r" % ret)

    def test_get_device_eojs(self):
        url = self._host + "/api/device/eojs"
        self.http_api_get(url)

    def test_get_device_the_eoj(self, eoj):
        url = self._host + "/api/device/eojs/" + eoj
        self.http_api_get(url)

    def test_get_device_eoj_epcs(self, eoj):
        url = self._host + "/api/device/eojs/" + eoj + "/epcs"
        self.http_api_get(url)

    def test_get_device_eoj_the_epc(self, eoj, epc):
        url = self._host + "/api/device/eojs/" + eoj + "/epcs/" + epc
        ret = self.http_api_get(url)
        logger.debug("%r" % (ret))

    def test_put_device_eoj_the_epc(self, eoj, epc, val):
        url = self._host + "/api/device/eojs/" + eoj + "/epcs/" + epc
        edt = "{\"edt\":\"%s\"}" % val
        #print("edt:%s" % edt)
        jsonData = json.loads(edt)
        self.http_api_put(url, jsonData)

def signal_handler(sig, frame):
    print('You pressed Ctrl+C!')
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)

    emuFeeder = EmuFeeder()
    
    if (gIsTest):
        emuFeeder.test()
        return

    if (emuFeeder.start()):
        emuFeeder.execute()


if __name__ == "__main__":
    main()