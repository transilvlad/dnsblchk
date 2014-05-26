# core libraries
import os
import sys
import time
import signal
import string
import __main__
import traceback
import threading
from email.utils import formatdate

# capture Exceptions
def except_catch(type, value, track, thread=None):
  ret = False
  if type != "SystemExit":
    # RFC822 error timestamp
    report = "Error time: " + formatdate(timeval=None, localtime=False, usegmt=True) + "\n"
    
    # thread no if set
    if thread != "":
      report += "Exception in thread: " + str(thread) + "\n\n"
    
    # get report
    rawreport = traceback.format_exception(type, value, track)
    report += "\n" . join(rawreport)
    
    # the string for logging
    ret = ("%s\n" + "-" * 30 + "\n\n") % report
  return ret
sys.excepthook = except_catch


# capture KeyboardInterrupt
def interrupt_catch(signal, frame):
  print ""
  os._exit(1)
signal.signal(signal.SIGINT, interrupt_catch)


# capture exit signal
def exit_catch(signal, frame):
  # tell children to shut down
  __main__.shutdown = True
  
  # wait for everything to terminate
  while True:
    if threading.activeCount() == 1:
      break
    else:
      time.sleep(2)
  
  # kill parent
  os._exit(1)
signal.signal(signal.SIGTERM, exit_catch)
