# MotionBoxPro

Our project aims to create a cheaper, more affordable MoCap system for indie teams using a hybrid approach between markerless and inertial motion capture. Designing our user interface with accessibility and a suite of convenient tools in mind, we hope to lower the requirement of technical understanding to operate our system. Seeking to utilize smartphone cameras, we plan to eliminate the excess costs that come with expensive, industry cameras and studio spaces typically associated with motion capture; we also plan to design easy-to-apply suits (similar to those used in inertial systems) at a much lower price than their industry counterparts.


## Installation Guide

### System Packages (Debian/Ubuntu)
```
debian@debian:~$ sudo apt install build-essential pkg-config
debian@debian:~$ sudo apt install python3-dev python3-venv
debian@debian:~$ sudo apt install libpq-dev                 # PostgreSQL client/build libs (psycopg2)
debian@debian:~$ sudo apt install nginx
debian@debian:~$ sudo apt install python3-certbot-nginx libaugeas0
debian@debian:~$ sudo apt install postgresql                # PostgreSQL
```

### System Packages (macOS)
Requires [Homebrew](https://brew.sh).
```
macos@macos:~$ brew install pkg-config
macos@macos:~$ brew install python@3.11
macos@macos:~$ brew install libpq          # PostgreSQL client/build libs (psycopg2)
macos@macos:~$ brew install nginx
macos@macos:~$ brew install certbot
macos@macos:~$ brew install postgresql@18  # PostgreSQL
```

### Certbot Setup (on the server)
```
debian@debian:~$ python3 -m venv /opt/certbot/
debian@debian:~$ /opt/certbot/bin/pip install --upgrade pip
debian@debian:~$ /opt/certbot/bin/pip install certbot
debian@debian:~$ ln -s /opt/certbot/bin/certbot /usr/bin/certbot
debian@debian:~$ certbot certonly --nginx
```

### Database Setup (PostgreSQL)
Current production database. Django connects with the `django.db.backends.postgresql` engine.
```
# Debian/Ubuntu
debian@debian:~$ sudo -u postgres psql
# macOS (Homebrew)
macos@macos:~$ psql postgres

postgres=# CREATE DATABASE db_name;
postgres=# CREATE USER username WITH PASSWORD 'password';
postgres=# GRANT ALL PRIVILEGES ON DATABASE db_name TO username;
postgres=# ALTER DATABASE db_name OWNER TO username;
postgres=# \c db_name
postgres=# GRANT ALL ON SCHEMA public TO username;
postgres=# \q
```
Note: you cannot `DROP DATABASE` while connected to it. Connect to another database first (`postgres` locally, `defaultdb` on DigitalOcean), then drop/create.

### .env
Make a copy from ./backend/.env_ and name it .env
Adjust settings as per your setup

### Project Setup
```
debian@debian:~$ cd ./
debian@debian:~$ python3 -m venv ./venv
debian@debian:~$ source ./venv/bin/activate
(venv) debian@debian:~$ pip install -r ./backend/requirements.txt
```

#### Migrate initial migrations
```
(venv) debian@debian:~$ cd ./backend
(venv) debian@debian:~$ python manage.py migrate
```

#### Create superuser
```
(venv) debian@debian:~$ cd ./backend
(venv) debian@debian:~$ python manage.py createsuperuser
```

## Local Development

### Running Development Servers

#### Backend Server
```
(venv) debian@debian:~$ cd ./backend
(venv) debian@debian:~$ python manage.py runserver
```

### Production App Server (gunicorn + uvicorn)
The production stack serves Django over ASGI with gunicorn managing uvicorn workers
(`motionboxpro/asgi.py` is the entrypoint). gunicorn and uvicorn are installed via `requirements.txt`.
```
(venv) debian@debian:~$ gunicorn motionboxpro.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --bind unix:/run/motionboxpro.sock \
    --workers 3 --timeout 60
```
nginx reverse-proxies to that socket (`proxy_pass`).

## Dedicated Server FAQ

#### Export a PostgreSQL database
`--clean --if-exists` makes the dump drop and recreate objects on import, so the target database does not need to be dropped first. Always single-quote the connection string (zsh treats `?` as a glob). On DigitalOcean append `?sslmode=require`.
```
debian@debian:~$ pg_dump 'postgresql://username:password@host:5432/database_name' --clean --if-exists --no-owner --no-privileges > data-dump.sql
```

#### Drop the public schema in a PostgreSQL database
```
debian@debian:~$ psql 'postgresql://username:password@host:5432/database_name' -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
```

#### Import a PostgreSQL database
```
debian@debian:~$ psql 'postgresql://username:password@host:5432/database_name' < data-dump.sql
```

#### Restart services
```
(venv) debian@debian:~$ sudo systemctl restart nginx
(venv) debian@debian:~$ sudo systemctl restart postgresql
(venv) debian@debian:~$ sudo systemctl restart motionboxpro        # gunicorn + uvicorn (app server)
```

## Contributing

### Development Workflow
1. Pull changes from `main`
```
debian@debian:~$ cd ./
debian@debian:~$ git switch main
debian@debian:~$ git pull
```
2. Create a new branch (see naming conventions below)
```
debian@debian:~$ git switch -c newbranch
```
3. Stage your files
```
debian@debian:~$ git add .
```
4. Create a commit
```
debian@debian:~$ git commit -m "message"
```
5. ONLY IF YOU WORKED ALONE IN YOUR BRANCH - Fetch changes
```
debian@debian:~$ git fetch origin
```
6. ONLY IF YOU WORKED ALONE IN YOUR BRANCH - Rebase against main - NEVER REBASE SHARED BRANCHES
```
debian@debian:~$ git rebase origin/main
```
7. Push your commit
```
debian@debian:~$ git push
```
8. On github - submit a pull request to `main`, request review from the team if needed

### Branch Strategy
- `main`: Main/development branch
- Features: `feature/feature-name`
- Bugs: `fix/bug-description`

### Code style
- Python: Follow PEP 8

#### Upgrading requirements.txt after installing/updating python package
```
(venv) debian@debian:~$ cd ./backend
(venv) debian@debian:~$ pip freeze > requirements.txt
```
