from pyFormulaClientNoNvidia import messages
from pyFormulaClientNoNvidia.FormulaClient import FormulaClient, ClientSource, SYSTEM_RUNNER_IPC_PORT

import os
import sys 

def main(message_file):
    client = FormulaClient(ClientSource.PERCEPTION, 
        read_from_file=message_file, write_to_file=os.devnull)
    conn = client.connect(SYSTEM_RUNNER_IPC_PORT)
    msg = messages.common.Message()
    try: 
        while not msg.data.Is(messages.server.ExitMessage.DESCRIPTOR):
            msg = conn.read_message()
            print(msg)
            if msg.data.Is(messages.perception.ConeMap.DESCRIPTOR):
                data = messages.perception.ConeMap()
                msg.data.Unpack(data)
                print(data)
    except : 
        pass


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("print_messages_file.py <message file>")
        exit(1)
    main(sys.argv[1])
