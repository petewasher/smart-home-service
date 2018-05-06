#! /bin/bash

sudo apt-get install -y apache2-utils
htpasswd -c .htpasswd smart-home-user
