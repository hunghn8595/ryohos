import threading
import time

class event_timer:

    ####################################################################################################
    #[Function]: Initiate timer
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   self {event_timer} - object of class enoceanCommunicator
    #   trigger {event} - Timer interrupt trigger
    #   period {int} - Timer period
    #[Return]: N/A
    ####################################################################################################
    def __init__(self, trigger, period, logger):
        self.logger = logger
        self.timer_process = threading.Thread(target=self.timer_setter, args=(trigger, period))
        self.timer_process.start()

    ####################################################################################################
    #[Function]: Periodically set the event to trigger publish flow
    #---------------------------------------------------------------------------------------------------
    #[Parameters]:
    #   trigger {event} - Timer interrupt trigger
    #   set_time {int} - Timer period
    #[Return]: N/A
    ####################################################################################################
    def timer_setter(self, trigger, set_time=60):
        TIME_OFFSET = 0.05
        while 1:
            try :
                # Trigger event object in AWS thread to publish status control data
                trigger.set()
            except Exception as err:
                self.logger.error("[Checking Status] Event cannot set, error: " + str(err))
            time.sleep(set_time-TIME_OFFSET)