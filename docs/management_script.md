1. Create an environment file:

```text
MYSQL_DATABASE=scholar_db
MYSQL_USER=scholar_user
MYSQL_PASSWORD=scholar_pass
MYSQL_ROOT_PASSWORD=rootpass
MYSQL_PORT=3306

```

2. Simple shell script to manage the Docker container:

```bash
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
esac

```

To use this setup:

1. Make sure you're in the `/` directory:

```bash
cd litratureSurvey
```

2. Make the management script executable:

```bash
chmod +x manage.sh
```

3. Start the MySQL container:

```bash
./manage.sh start
```

The directory structure will look like this:

```
/
├── docker-compose.yaml
├── .env
├── manage.sh
└── init/
    └── 01_schema.sql
```

To interact with the database, you can:

1. Use the management script:

   - `./manage.sh start` - Start the container
   - `./manage.sh stop` - Stop the container
   - `./manage.sh logs` - View logs
   - `./manage.sh clean` - Remove container and volume

2. Connect to the database:

```bash
mysql -h localhost -P 3306 -u scholar_user -p scholar_db
```
