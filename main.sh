#!/bin/bash
# chkconfig: 2345 95 20
# description: start, stop, status and restart
# processname: DNS Black List Checker
# name: dnsblchk

# Configuration variables
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRV="dnsblchk"
PTH="$DIR""/main.py"


# Needed variables
EXC="python $PTH"
PSI="ps -eo pid,args | grep $PTH | grep -v grep | awk '{print $""1}'"
GRP=`eval $PSI`
SPN='-\|/'
PID=0


# If service found secure PID
if [ ! -z $GRP ]
then
  PID=`expr $GRP | sed -e "s/ //g"`
fi


# Main conditions
case "$1" in
    start)
      if [ $PID == 0 ]
      then
        $EXC &
        echo -ne "Starting $SRV"
        sleep 1
        
        GNP=`eval $PSI`
        if [ ! -z $GNP ]
        then
          printf "%50s" "  [  $(tput setaf 2)OK$(tput sgr0)  ]  "
        else
          printf "%50s" "  [  $(tput setaf 1)FAILED$(tput sgr0)  ]  "
        fi
      
      else
        echo -ne "$SRV (pid $PID) is running..."
      
      fi
      echo ""
  ;;
    stop)
      if [ $PID == 0 ]
      then
        echo -ne "$SRV is stopped... nothing to stop"
      
      else
        echo -ne "Stopping $SRV  "
        kill $PID
        
        i=0
        while :
        do
          sleep 0.02
          
          GNP=`eval $PSI`
          if [ -z $GNP ]
          then
            break
          fi
          
          i=$(( (i+1) %4 ))
          printf "\b${SPN:$i:1}"
          
        done
        printf "\b\b"
        printf "%50s" "  [  $(tput setaf 2)OK$(tput sgr0)  ]  "
      
      fi
      echo ""
  ;;
    restart)
      if [ $PID == 0 ]
      then
        echo "$SRV is stopped... sending start command"
        
      else
        echo -ne "Stopping $SRV    "
        kill $PID
        
        i=0
        NID=0
        while :
        do
          sleep 0.02
          
          GNP=`eval $PSI`
          if [ ! -z $GNP ]
          then
            NID=`expr $GNP | sed -e "s/ //g"`
          fi
          
          if [ $NID > 0 ] && [ $NID != $PID ]
          then
            break
          fi
          
          i=$(( (i+1) %4 ))
          printf "\b${SPN:$i:1}"
          
        done
        printf "\b\b"
        printf "%48s" "  [  $(tput setaf 2)OK$(tput sgr0)  ]  "
        echo ""
      
      fi
      
      $EXC &
      echo -ne "Starting $SRV"
      sleep 1
      
      GNP=`eval $PSI`
      if [ ! -z $GNP ]
      then
        printf "%50s" "  [  $(tput setaf 2)OK$(tput sgr0)  ]  "
        echo ""
        echo "$SRV (pid $GNP) is running..."
      
      else
        printf "%50s" "  [  $(tput setaf 1)FAILED$(tput sgr0)  ]  "
        echo ""
      
      fi
  ;;
    status)
      if [ $PID == 0 ]
      then
        echo "$SRV is stopped"
      
      else
        echo "$SRV (pid $PID) is running..."
      fi
  ;;
    *)
      echo "Usage: $SRV {start|stop|restart|status}"
      exit 1
  ;;
esac

exit