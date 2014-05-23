import smtplib
import string
import random
import time
from email.utils import formatdate

_smtp_host = 'localhost'
_smtp_port = 25

# The function used to Initialize this module
def mail_init(smtp_host, smtp_port):
  global _smtp_host, _smtp_port
  
  _smtp_host = smtp_host
  _smtp_port = smtp_port

  

# The send mail function
def mail_plain(to_email, from_email, subject, message, to_name = "", from_name = ""):

  # MIME header
  headers = "MIME-Version: 1.0" + "\r\n"

  # message ID header
  from_address, from_domain = string.split(from_email, "@")
  headers  += "Message-Id: " + str(time.time()) + "." + \
  ("".join(random.choice("0123456789ABCDEF") for i in range(16))) + \
  "@" + from_domain + "\r\n"
  
  # Date Header
  headers += "Date: " + formatdate(timeval=None, localtime=False, usegmt=True) + "\r\n"

  # required headers
  headers += "From: " + from_name + " <" + from_email + ">\r\n"
  headers += "To: " + to_name + " <" + to_email + ">\r\n"
  headers += "Subject: " + subject + "\r\n"

  # content header
  headers += "Content-Type: text/plain; charset=UTF-8\r\n"
  headers += "\r\n"

  # try to send
  try:
    connection = smtplib.SMTP(_smtp_host, _smtp_port)
    connection.sendmail(from_email, [to_email], headers + message)
    return [True]

  # get exception
  except Exception, exc:
    return [False, exc]