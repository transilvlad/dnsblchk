import dns.resolver
import dns.reversename


# DNS resolver used to check if an IP is blacklisted or not
def dnsbl(ip, server):
  lst = [server]
  
  # if IPv4
  if ip.find('.') > -1:
  
    # check if there is an IPv4 mapped as IPv6
    ip = ip.replace('::ffff:', '')
  
    # reverse IP
    splits = ip.split('.')
    splits.reverse()
    revip  = '.'.join(splits)
    
  else:
    # it is IPv6 formatted
    revip = dns.reversename.from_address(ip)
    revip = '.'.join(revip[0:32])
  
  # prepare query
  suspip = revip + '.' + server
  
  # instance
  mkr = dns.resolver.Resolver()
  mkr.nameservers = ['192.168.0.1']
  
  # Please note that the answer is returned in the A record, not in the AAAA
  # http://www.spamhaus.org/organization/statement/012/spamhaus-ipv6-blocklists-strategy-statement
  
  try:
    try:
      # Make the DNS query
      res = mkr.query(suspip, 'A')
    except dns.resolver.NXDOMAIN:
      # Not Listed
      return False
    
    # Listed
    for rdata in res:
      lst.append(rdata.address) # A
    lst.append('R')
    
    return lst
  
  except:
    # Not Listed
    return False
