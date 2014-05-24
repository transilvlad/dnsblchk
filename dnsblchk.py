import os
import sys
import time


from config import *
from signals import *
from mail_lib import *
from dnsbl_lib import *
from file_handlers import *

# A global variable used to check if shutdown was signaled
shutdown = False

# The main DNSBL Handler
def dnsblk_handler(servers, ips):
  
  # check the shutdown flag
  if shutdown == False:
    try:
      
      # A dictionary used to store the listed IP addresses
      listed_ips = {}
      
      ###
      log_file_handler = None
      csvwriter = None
      
      # for each DNSBL server...
      for server in servers:
        
        # check again the shutdown flag
        if shutdown == True:
          break
      
        # for each IP address we want to query...
        for ip in ips:
        
          # Check the IP address against a DNSBL server
          ret = dnsbl(ip[0], server[0])
          
          # if the IP IS listed
          if ret is not False:
            if log_file_handler is None:
              log_file_handler = open(dnsblk_log + str(int(time.time())) + ".log", 'wb')
              csvwriter = csv.writer(log_file_handler, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
              
            csvwriter.writerow([time.strftime("%d %b %Y %H:%M:%S", time.gmtime()), ip[0], server[0], ret[1]])
            log_file_handler.flush()
            
            # add the IP and the server in the previous defined dictionary
            if ip[0] not in listed_ips:
              listed_ips[ip[0]] = []
            listed_ips[ip[0]].append(server[0])
            
          # sleep for a short time after each query
          time.sleep(0.01)
          
          
      if log_file_handler is not None:
        log_file_handler.close()
      
      # If there are listed IP addresses, notice each administrator by email
      if len(listed_ips) > 0:
        
        # compose the email text
        mail_text = ""
        for x in listed_ips:
          mail_text += x + ' ===> ' + ", ".join(listed_ips[x]) + "\r\n"
        
        # and send the email to each administrator
        for recipient in dnsblk_recipients:
          ret = mail_plain(recipient, dnsblk_from, "Dnsblchk ALERT", mail_text)
          
          if not ret[0]:
            loggError(dnsblk_error_log, "Mailer error: " + str(ret[1]))

    
    except:
      exc_type, exc_value, exc_traceback = sys.exc_info()
      ret = except_catch(exc_type.__name__, exc_value, exc_traceback)
      if ret != False:
        loggError(dnsblk_error_log, ret)



    
# Main Program
if __name__ == "__main__":
  
  # Initialize the mail module
  mail_init(dnsblk_smtp_host, dnsblk_smtp_port)

  # Load the DNSBL servers and the IP addresses which will be checked
  servers = load_csv(dnsblk_servers)
  ips     = load_csv(dnsblk_ips)

  # Run forever (until shutdown will be fired)
  while True:
    
    # check the shutdown flag
    if shutdown:
      break
      
      
    # a counter variable used below
    wait_counter = 0
  
    try:
      # Run the DNSBL checks
      dnsblk_handler(servers, ips)
      
      
      # wait a number of hours
      # the whole period of time is divided in small chunks of 10 seconds
      # to allow us to check if the shutdown was fired
      while wait_counter < (dnsblk_sleep * 60 * 60):
        if shutdown:
          break
      
        time.sleep(10)
        wait_counter += 10

    except:
      exc_type, exc_value, exc_traceback = sys.exc_info()
      ret = except_catch(exc_type.__name__, exc_value, exc_traceback)
      if ret != False:
        loggError(dnsblk_error_log, ret)
        