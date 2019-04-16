@startuml
p2p_server -> client1: Notify Client
p2p_server -> client2: Notify Client
loop
  p2p_server -> p2p_server: Get one available client
  p2p_server -> client1: Ask Status
  client1 -> p2p_server: No File.
  p2p_server -> client1: Send File
end
client1 -> client1: Act as server
@enduml


Treedist model