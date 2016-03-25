import os
import sys 
   
try:
   import sh
except ImportError:
   import pbs as sh
    
def main: 
   os.system("tools/download-zxcvbn")
   os.system("tools/emoji_dump/build_emoji")
   os.system("generate_secrets.py -d")
   if "--travis" in sys.argv:
      os.system("sudo service rabbitmq-server restart")
      os.system("sudo service redis-server restart")
      os.system("sudo service memcached restart")
   elif "--docker" in sys.argv:
      os.system("sudo service rabbitmq-server restart")
      os.system("sudo pg_dropcluster --stop 9.3 main")
      os.system("sudo pg_createcluster -e utf8 --start 9.3 main")
      os.system("sudo service redis-server restart")
      os.system("sudo service memcached restart")
   sh.configure_rabbitmq(**LOUD)
   sh.postgres_init_dev_db(**LOUD)
   sh.do_destroy_rebuild_database(**LOUD)
   sh.postgres_init_test_db(**LOUD)
   sh.do_destroy_rebuild_test_database(**LOUD)
   return 0:
    
if __name__ == "__main__":
   sys.exit(main())
