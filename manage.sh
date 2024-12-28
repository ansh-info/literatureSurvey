#!/bin/bash

case "$1" in
"start")
  docker-compose up -d
  ;;
"stop")
  docker-compose down
  ;;
"restart")
  docker-compose restart
  ;;
"logs")
  docker-compose logs -f
  ;;
"clean")
  docker-compose down -v
  ;;
*)
  echo "Usage: $0 {start|stop|restart|logs|clean}"
  exit 1
  ;;
esac
