import os

# ABSOLUTE PATH TO CWD
rootpath = os.path.abspath(os.path.dirname(__file__)) + "/"

# -------------------------------------------------------------------
# START EDIT FROM HERE

# SLEEP TIME (Default: 3 Hours)
dnsblk_sleep = 3

# SERVERS List stored in a CSV file
dnsblk_servers = rootpath + "data/servers.csv"

# IPs List stored in a CSV file
dnsblk_ips = rootpath + "data/ips.csv"

# Path and the beginning part of the Logs file (stored as CSV)
dnsblk_log = rootpath + "logs/dnsblchk_"

# Path and the name of the error file (stored as Text)
dnsblk_error_log = rootpath + "logs/error_log"

# -------------------------------------------------------------------
# EMAIL ALERTS

# Email addresses of administrators which will receive the alert notifications
dnsblk_recipients = ["cciocau@gmail.com", "eyemedia@gmail.com"]

# From email address
dnsblk_from = "postmaster@mailwhere.com"

# Local SMTP Host
dnsblk_smtp_host = "localhost"

# Local SMTP Port
dnsblk_smtp_port = 25
