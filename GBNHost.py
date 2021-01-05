from Simulator import Simulator, EventEntity
from enum import Enum
from struct import pack, unpack

# In this class you will implement a full-duplex Go-Back-N client. Full-duplex means that this client can 
# both send and receive data. You are responsible for implementing a Go-Back-N protocol in a simulated
# Transport layer. We are not going to use real network calls in this project, as we want to precisely 
# simulate when packet delay, loss, and corruption occurs. As such, your simulated transport protocol
# will interface with the Simulator object to communicate with simulated Application and Network layers.
#

# The Simulator will call three functions that you are responsible for implementing. These functions define
# the interface by which the simulated Application and Network layers communicate with your transport layer:
# - receive_from_application_layer(payload) will be called when the Simulator has new data from the application
#   layer that needs to be sent across the network
# - receive_from_network_layer(byte_data) will be called when the Simulator has received a new packet from the
#   network layer that the transport layer needs to process
# - timer_interrupt() will be called when the Simulator detects that a timer has expired 


# Your code can communicate with the Simulator by calling four methods:
# - Call self.simulator.pass_to_application_layer(data) when your Transport layer has successfully received and processed
#   a data packet from the other host that needs to be delivered up to the Application layer
#    * pass_to_application_layer(data) expects to receive the payload of a packet as a decoded string, not as the bytes object 
#      generated by unpack
# - Call self.simulator.pass_to_network_layer(byte_data) when your Transport layer has created a data packet or an ACK packet
#   that needs to be sent across the network to the other host
#    * pass_to_network_layer() expects to receive a packet that has been converted into a bytes object using pack. See the
#      next section in this comment for more detail
# - Call self.simulator.start_timer(self.entity, self.timer_interval) when you want to start a timer
# - Call self.simulator.stop_timer(self.entity) when you want to stop the running timer


# You will need to write code to pack/unpack data into a byte representation appropriate for 
# communication across a network. For this assignment, you will assume that all packets use the following header:
# - Sequence Number (int)           -- Set to 0 if this is an ACK
# - Acknowledgement Number (int)    -- Set to 0 if this is not an ACK
# - Checksum (half)                 -- Compute a UDP Checksum, as discussed in class
# - Acknowledgement Flag (boolean)  -- Set to True if sending an ACK, otherwise False
# - *Payload* length, in bytes (int)  -- Set this to 0 when sending an ACK message, as these will not carry a payload
# - Payload (string)                -- Leave this empty when sending an ACK message
# When unpacking data in this format, it is recommended to first unpack the fixed length header. After unpacking the
# header, you can determine if there is a payload, based on the size of Payload Length.
# NOTE: It is possible for payload length to be corrupted. In this case, you will get an Exception similar to
#       "unpack requires a buffer of ##### bytes". If you receive this exception, this is a sign that the packet is
#       corrupt. This is not the only way the packet can be corrupted, but is a special case of corruption that will
#       prevent you from unpacking the payload. If you can unpack the payload, use the checksum to determine if the
#       packet is corrupted. If you CAN'T unpack the payload, then you already KNOW that the packet is corrupted.


# Finally, you will need to implement the UDP Checksum algorithm to check for corruption in your packets. 
# As discussed in class, sum each of the 16-bit words of the packet, carrying around any overflow bits. Once you 
# have summed all of the 16-bit words, perform the 1's complement. If a packet contains an odd number of bytes 
# (i.e. the last byte doesn't fit into a 16-bit word), pad the packet (when computing the checksum) with a 0 byte. 
# When receiving a packet, check that it is valid using this checksum.


# NOTE: By default, all of the test cases created for this program capture print() output and save it in a log
#       file with the same name as the test case being run. This will prevent you from printing to the terminal
#       while your code is running (your print statements will be added to the log file instead)
#       You can disable this functionality by editing the test*.cfg file you are working on and removing the  
#       --capture_log argument (just delete it). Do NOT change any other of the option parameters in test*.cfg


class GBNHost():

    # The __init__ method accepts:
    # - a reference to the simulator object
    # - the name for this entity (EntityType.A or EntityType.B)
    # - the interval for this entity's timer
    # - the size of the window used for the Go-Back-N algorithm
    def __init__(self, simulator, entity, timer_interval, window_size):
        
        # These are important state values that you will need to use in your code
        self.simulator = simulator
        self.entity = entity
        
        # Sender properties
        self.timer_interval = timer_interval        # The duration the timer lasts before triggering
        self.window_size = window_size              # The size of the seq/ack window
        self.window_base = 0                        # The last ACKed packet. This starts at 0 because no packets 
                                                    # have been ACKed
        self.next_seq_num = 1                       # The SEQ number that will be used next
        self.unACKed_buffer = {}                    # A buffer that stores all sent but unACKed packets
        self.app_layer_buffer = []                  # A buffer that stores all data received from the application 
                                                    #layer that hasn't yet been sent
        
        # Receiver properties
        self.expected_seq_number = 1                # The next SEQ number expected

        # NOTE: Do not edit/remove any of the code in __init__ ABOVE this line. You need to edit the line below this
        #       and may add other functionality here if so desired

        self.current_seq_number = 1
        packet = pack('!iiH?i', 0, 0, self.checksum(pack('iiH?i', 0, 0, 0, True, 0)), True, 0)
        self.last_ACK_pkt = packet                    # TODO: The last ACK pkt sent. You should initialize this to a
                                                    # packet with ACK = 0 in case an error occurs on the first packet received. 
                                                    # If that occurs, this default ACK can be sent in response
   
    
 # HELPER FUNCTIONS
 # ################################################################################################################################   
    def make_pkt(self, seq_num = 0, ack = 0, payload=''):
        checksum = self.checksum(pack('!iiH?i%is' % len(payload), seq_num, ack, 0, ack != 0, len(payload), payload.encode()))
        newPayload = pack('!iiH?i%is' % len(payload), seq_num, ack, checksum, ack != 0,len(payload), payload.encode())
        return newPayload

    def checksum(self, packet):
        check = 0x0000
        
        # If we have an odd number of bytes, pad the packet with 0x0000
        padded_pkt = None
        if len(packet) % 2 == 1:
            padded_pkt = packet + bytes(1)
        else:
            padded_pkt = packet

        for i in range(0, len(padded_pkt), 2):
            w = padded_pkt[i] << 8 | padded_pkt[i+1]
            check = self.carry_around_add(check, w)
        return ~check & 0xffff

    def carry_around_add(self, a, b):
        c = a + b
        return (c & 0xffff) + (c >> 16)

    def corrupted(self, packet):
        if self.checksum(packet) == 0x0000:
            return False
        else:
            return True
    
    def isAck(self, byte_data):
        isItAck = unpack('!iiH?i', byte_data[:15])[3] or 0
        return isItAck

    
    def getSeqNum(self, byte_data):
        seq_num = unpack('!iiH?i', byte_data[:15])[0] or 0
        return seq_num

    
    def getAckNum(self, byte_data):
        ack_num = unpack('!iiH?i', byte_data[:15])[1] or 0
        return ack_num

   
    def extract_payload(self, byte_data):
        length = unpack('!iiH?i', byte_data[:15])[4] or 0
        emptyChar = ''
        if length > 0:
            try:
                tryVar = unpack('!%ds' % length, byte_data[15:])[0].decode()
                return tryVar
            except:
                return emptyChar
        else:
            return emptyChar

    
# REQUIRED CORE FUNCTIONS
###################################################################################################

    # TODO: Complete this function
    # This function implements the SENDING functionality. It should implement retransmit-on-timeout. 
    # Refer to the GBN sender flowchart for details about how this function should be implemented
    def receive_from_application_layer(self, payload):
        if self.next_seq_num < self.window_size + self.window_base:
            self.unACKed_buffer[self.next_seq_num] = self.make_pkt(
                seq_num=self.next_seq_num, payload=payload)
            self.simulator.pass_to_network_layer(
                self.entity, self.unACKed_buffer[self.next_seq_num], False)
            if self.window_base + 1 == self.next_seq_num:
                self.simulator.start_timer(self.entity, self.timer_interval)
            self.next_seq_num = self.next_seq_num + 1
        else:
            self.app_layer_buffer.append(payload)


    # TODO: Complete this function
    # This function implements the RECEIVING functionality. This function will be more complex that
    # receive_from_application_layer(), it includes functionality from both the GBN Sender and GBN receiver
    # FSM's (both of these have events that trigger on receive_from_network_layer). You will need to handle 
    # data differently depending on if it is a packet containing data, or if it is an ACK.
    # Refer to the GBN receiver flowchart for details about how to implement responding to data pkts, and
    # refer to the GBN sender flowchart for details about how to implement responidng to ACKs
    def receive_from_network_layer(self, byte_data):
        if not self.corrupted(byte_data) and self.isAck(byte_data):
            if self.window_base + 1 <= self.getAckNum(byte_data):
                tempVar = self.window_base + 1
                while self.getAckNum(byte_data) >= tempVar:
                    if tempVar in self.unACKed_buffer.keys():
                        del self.unACKed_buffer[tempVar]
                        tempVar = tempVar + 1
                self.window_base = self.getAckNum(byte_data)
                self.simulator.stop_timer(self.entity)

            if self.next_seq_num != self.window_base + 1:
                self.simulator.start_timer(self.entity, self.timer_interval)

            while self.window_base + self.window_size > self.next_seq_num and len(self.app_layer_buffer) > 0:
                payload = self.app_layer_buffer.pop()
                self.unACKed_buffer[self.next_seq_num] = self.make_pkt(
                    seq_num=self.next_seq_num, payload=payload)
                self.simulator.pass_to_network_layer(
                    self.entity, self.unACKed_buffer[self.next_seq_num], False)
                if self.window_base == self.next_seq_num:
                    self.simulator.start_timer(
                        self.entity, self.timer_interval)
                self.next_seq_num = self.next_seq_num + 1
        elif self.expected_seq_number != self.getSeqNum(byte_data):
            self.simulator.pass_to_network_layer(
                self.entity, self.last_ACK_pkt, True)
        elif self.corrupted(byte_data):
            self.simulator.pass_to_network_layer(
                self.entity, self.last_ACK_pkt, True)
        else:
            data = self.extract_payload(byte_data)
            self.simulator.pass_to_application_layer(self.entity, data)
            self.last_ACK_pkt = self.make_pkt(ack=self.expected_seq_number)
            self.simulator.pass_to_network_layer(
                self.entity, self.last_ACK_pkt, True)
            self.expected_seq_number = self.expected_seq_number + 1


    # TODO: Complete this function
    # This function is called by the simulator when a timer interrupt is triggered due to an ACK not being 
    # received in the expected time frame. All unACKed data should be resent, and the timer restarted
    def timer_interrupt(self):
        test = False
        for value in self.unACKed_buffer.values():
            self.simulator.pass_to_network_layer(self.entity, value, False)
            test = True
        if test:
            self.simulator.start_timer(self.entity, self.timer_interval)

    
    


    