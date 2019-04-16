from xmlrpc.client import ServerProxy, Binary
from socketserver import ThreadingMixIn
import socket
from xmlrpc.server import SimpleXMLRPCServer
import threading
import logging
import os.path
from cmd import Cmd
import argparse

PREFIX_PATH = './tmp/'

def get_host_ip():
  try:
      s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      s.connect(('8.8.8.8', 80))
      ip = s.getsockname()[0]
  finally:
      s.close()

  return ip


class Node:
  def __init__(self, address):
    logging.debug("Create node "+str(address))
    self.__exit = False
    self.__host, self.__port = address
    self.__know_list = []
    self.__history = []
    self.__file_name = ''
    self.__lock = threading.Lock()
    self.__sema = threading.Semaphore(value = 0)
    self.__deploy_thread = threading.Thread(target = self.start_deploy)
    self.__deploy_thread.daemon = True
    self.__deploy_thread.start()
    self.__data = b''
  
  def __del__(self):
    self.__exit = True
    self.__sema.release()
    self.__deploy_thread.join()
  
  def start(self):
    logging.debug('')
    server = SimpleXMLRPCServer((self.__host, self.__port), logRequests = False)
    server.register_instance(self)
    server.serve_forever()
  
  def register_client(self, client_ip, client_port):
    logging.info("Client %s:%d register."%(client_ip, client_port))
    if self.__know_list.count((client_ip, client_port)):
      return False
    self.__know_list.append((client_ip, client_port))
    return True
  
  def unregister_client(self, client):
    self.__know_list.append(client)
    return True

  def prepare_to_receive_file(self, file):
    logging.debug('')
    with self.__lock:
      if file == self.__file_name:
        return False
      self.__file_name = file
      return True

  def __find_available_client(self, file):
    for know in self.__know_list:
      if know in self.__history:
        continue
      know_ip, know_port = know
      logging.debug('Asking '+ str(know))
      server = ServerProxy('http://'+str(know_ip)+':'+str(know_port))
      if (server.prepare_to_receive_file(file)):
        self.__history.append(know)
        yield server
  
  def put_file(self, data, know_node_list, history_list):
    for (node_ip, node_port) in know_node_list:
      if node_ip != self.__host or node_port != self.__port:
        self.register_client(node_ip, node_port)
      else:
        self.__history.append((node_ip, node_port))
    
    for history in history_list:
      self.__history.append(history)

    if not os.path.exists(PREFIX_PATH):
      os.mkdir(PREFIX_PATH)

    self.__data = data.data
    file_name = PREFIX_PATH + os.path.basename(self.__file_name)
    with open(file_name, 'wb') as file_to_write:
      file_to_write.write(self.__data)
      logging.info("Write file complete")
      self.__sema.release()
      return True
    logging.error("Failed to open file %s"%self.__file_name)
    return False
  
  def start_deploy(self):
    while not self.__exit:
      self.__sema.acquire()
      if self.__exit:
        break;
      logging.info("Start to deploy")
      if not self.__data:
        logging.error("File not exist. Please receive file first.")
      else:
        for available_client in self.__find_available_client(self.__file_name):
          available_client.put_file(Binary(self.__data), self.__know_list, self.__history)

      self.__file_name = ''
      self.__data = b''
      logging.info("Deploy finished")
    return True

class CommandHandler(Cmd):
  def __init__(self, node):
    super(CommandHandler, self).__init__()
    self.__node = node

  def do_exit(self, arg):
    logging.error("Bye")
    return True

  def do_deploy(self, arg):
    file_name = arg
    if not os.path.exists(file_name):
      logging.error("File %s not exist."%file_name)
      return False
    if self.__node.prepare_to_receive_file(file_name):
      with open(file_name, 'rb') as file_to_read:
        logging.debug('Put file')
        self.__node.put_file(Binary(file_to_read.read()), [], [])
    else:
      logging.error("Server prepare failed.")
  
def main(args):
  LOG_FORMAT = "[%(asctime)s:%(levelname)s:%(funcName)s]  %(message)s"
  log_level = logging.INFO
  if args.debug:
    log_level = logging.DEBUG

  logging.basicConfig(level=log_level, format=LOG_FORMAT)

  if not args.address:
    logging.critical("Need server address as input, like \"127.0.0.1:60001\"")
    arg_parser.print_help()
    exit()

  server_ip, server_port = args.address.split(':')
  server_port = int(server_port)
  
  if args.client:
    if args.port:
      client_port = args.port
    else:
      client_port = 6000
    node = Node((get_host_ip(), client_port))
    client_serve_thread = threading.Thread(target = node.start)
    client_serve_thread.daemon = True
    client_serve_thread.start()
    logging.debug("Client")
    server_proxy = ServerProxy('http://'+str(server_ip)+":"+str(server_port))
    server_proxy.register_client(get_host_ip(), client_port)
    client_serve_thread.join()
  elif args.server:
    node = Node((server_ip, server_port))
    server_thread = threading.Thread(target = node.start)
    server_thread.daemon = True
    server_thread.start()
    logging.debug("Server")
    command_handler = CommandHandler(node)
    command_handler.cmdloop()
    server_thread.join()


if __name__ == "__main__":
  arg_parser = argparse.ArgumentParser(description="manual to this script")
  arg_parser.add_argument('-c', "--client", help="run in client mode",
                          action="store_true")
  arg_parser.add_argument('-s', "--server", help="run in server mode",
                          action="store_true")
  arg_parser.add_argument('-d', "--debug", help="enable debug mode",
                          action="store_true")
  arg_parser.add_argument('-a', "--address", help="server address",
                          type=str)
  arg_parser.add_argument('-p', "--port", help="client port",
                          type=int)
  args = arg_parser.parse_args()

  if not args.client and not args.server:
      logging.warning("Run in qpython as client mode")
      args.client=True
      args.address="172.18.93.85:60000"
      args.debug=True
  main(args)
