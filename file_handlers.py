import csv
import time
    
    
# The function which will append rows to the error log file
def loggError(file_name, data):
  with open(file_name, 'a') as error_log:
    error_log.write(_timemark() + " - " + data + "\r\n")
    error_log.flush()
    

# This function will load all data from a CSV file 
def load_csv(servers_file):
  result = []

  with open(servers_file, 'rb') as csvfile:
   csvreader = csv.reader(csvfile, delimiter=',', quotechar='"')
   for row in csvreader:
      result.append(row)
      
      
  return result
  
# A small function used to format the Date
def _timemark():
  t = time.gmtime()

  return time.strftime("%d %b %Y %H:%M:%S", t)