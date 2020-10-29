import json
import os
import sys

def write_header():
    f.write('# argv\n')
    f.write('import sys, os, inspect\n')
    f.write('device_num = int(sys.argv[1])\n')
    f.write('port = int(sys.argv[3])\n')
    f.write('# PyTorch\n')
    f.write('import torch\n')
    f.write('import torch.nn as nn\n')
    f.write('import torch.nn.functional as F\n')
    f.write('# communication\n')
    f.write('from socket import *\n')
    f.write('import struct\n')
    f.write('HOST = sys.argv[2]\n')
    f.write('PORT = port\n')
    f.write('# works\n')
    f.write('from PIL import Image\n')
    f.write('import numpy as np\n')
    f.write('import threading\n')
    f.write('import pickle\n')
    f.write('from pathlib import Path\n\n')
    
def write_relu():
    f.write('def relu(x):\n')
    f.write('\treturn np.maximum(x, 0)\n\n')

def write_net():
    f.write('class Net(nn.Module):\n')
    f.write('\tdef __init__(self):\n')
    f.write('\t\tsuper(Net, self).__init__()\n')
    conv_idx = 1
    pool_idx = 1
    fc_idx = 1
    for layer_idx, layer in enumerate(data['layers']):
        if layer == 'conv':
            f.write('\t\tself.conv%d = nn.Conv2d(in_channels=%d, out_channels=%d, kernel_size=%d, stride=%d, padding=0)\n' 
                    % (conv_idx, data['in_channel'][layer_idx], data['out_channel'][layer_idx], data['filter'][layer_idx], data['stride'][layer_idx]))
            conv_idx += 1
        elif layer == 'pool':
            f.write('\t\tself.pool%d = nn.MaxPool2d(kernel_size=%d, stride=%d)\n' % (pool_idx, data['filter'][layer_idx], data['stride'][layer_idx]))
            pool_idx += 1
        elif layer == 'FL':
            f.write('\t\tself.fc%d = nn.Linear(%d, %d)\n' % (fc_idx, data['in_channel'][layer_idx], data['out_channel'][layer_idx]))
            fc_idx += 1
    f.write('\n')

def write_recvall():
    f.write('def recvall(sock):\n')
    f.write('\t# Read message length and unpack it into an integer\n')
    f.write('\traw_msglen = recv(sock, 4)\n')
    f.write('\tif not raw_msglen:\n')
    f.write('\t\treturn None\n')
    f.write('\tmsglen = struct.unpack(\'>I\', raw_msglen)[0]\n')
    f.write('\t# Read the message data\n')
    f.write('\treturn recv(sock, msglen)\n\n')

def write_recv():
    f.write('def recv(sock, n):\n')
    f.write('\t# Helper function to recv n bytes or return None if EOF is hit\n')
    f.write('\tdata = bytearray()\n')
    f.write('\twhile len(data) < n:\n')
    f.write('\t\tpacket = sock.recv(n - len(data))\n')
    f.write('\t\tif not packet:\n')
    f.write('\t\t\treturn None\n')
    f.write('\t\tdata.extend(packet)\n')
    f.write('\treturn data\n\n')

def write_sendall():
    f.write('def sendall(sock, msg):\n')
    f.write('\tmsg = struct.pack(\'>I\', len(msg)) + msg\n')
    f.write('\tsock.sendall(msg)\n\n')

def write_job():
    f.write('def job(conn, condition):\n')
    f.write('\t# print(conn)\n')
    f.write('\tglobal cnt\n')
    f.write('\tglobal offset\n')
    f.write('\tglobal x\n')
    f.write('\tglobal y\n')
    f.write('\tglobal device_num\n')
    f.write('\twhile True:\n')
    f.write('\t\ttry:\n')
    f.write('\t\t\tbytes = recvall(conn)\n')
    f.write('\t\t\tif bytes is None:\n')
    f.write('\t\t\t\tbreak\n')
    f.write('\t\texcept ConnectionResetError:\n')
    f.write('\t\t\tbreak\n')
    f.write('\t\tdata = pickle.loads(bytes)\n')
    f.write('\t\tkey = data[\'key\']\n')
    f.write('\t\tblock_id = data[\'blkId\']\n')
    f.write('\t\tidx = data[\'id\']\n')
    f.write('\t\tdata_from_device = data[\'data\']\n')
    f.write('\t\tif key == \'get\':\n')
    f.write('\t\t\t# merge data\n')
    f.write('\t\t\tcondition.acquire()\n')
    f.write('\t\t\tcnt += 1\n')
    f.write('\t\t\tif data_from_device is not None:\n')
    f.write('\t\t\t\t# print(data_from_device.shape)\n')
    layer_key = []
    for block_idx, key in enumerate(data['devices'][0]):
        layer_key.append(key)
    # print(layer_key)
    for block_idx in range(total_block_num+1):
        begin = 0
        end = 0
        if block_idx-1 >= 0:
            begin = int(layer_key[block_idx-1].split(',')[0])
            end = int(layer_key[block_idx-1].split(',')[1])
        # print(block_idx)
        # print(end)
        # print(data['layers'][end])
        if block_idx == 0:
            continue
        elif block_idx == 1:
            f.write('\t\t\t\tif block_id == %d:\n' % (block_idx))
        else:
            f.write('\t\t\t\telif block_id == %d:\n' % (block_idx))
        f.write('\t\t\t\t\tif cnt == 1:\n')
        if data['layers'][end] == 'conv' or data['layers'][end] == 'pool':
            f.write('\t\t\t\t\t\tx = torch.ones(1, %d, %d, %d)\n' % (data['out_channel'][end], data['output'][end], data['output'][end]))
        elif data['layers'][end] == 'FL':
            f.write('\t\t\t\t\t\tx = np.zeros(%d)\n' % (data['out_channel'][end]))
        if data['layers'][end] == 'conv' or data['layers'][end] == 'pool':
            for device_idx in range(total_device_num):
                if device_idx == 0:
                    f.write('\t\t\t\t\tif idx == %d:\n' % (device_idx))
                else:
                    f.write('\t\t\t\t\telif idx == %d:\n' % (device_idx))
                number_of_layer_in_block = len(data['padding_info'][device_idx][layer_key[block_idx-1]])
                f.write('\t\t\t\t\t\tx[:, :, %d:%d, :] = data_from_device\n' 
                        %(data['padding_info'][device_idx][layer_key[block_idx-1]][number_of_layer_in_block-1][0], data['padding_info'][device_idx][layer_key[block_idx-1]][number_of_layer_in_block-1][1]+1))
        elif data['layers'][end] == 'FL':
            f.write('\t\t\t\t\tx += data_from_device\n')
    f.write('\t\t\tif cnt < device_num:\n')    
    f.write('\t\t\t\tcondition.wait()\n')  
    f.write('\t\t\tif cnt == device_num:\n')  
    f.write('\t\t\t\tcondition.notifyAll()\n')  
    f.write('\t\t\t\tcnt = 0\n')  
    f.write('\t\t\tcondition.release()\n')  
    f.write('\t\t\t# print(idx, cnt)\n')
    f.write('\t\t\t# group[data[\'id\']] = conn\n')
    f.write('\t\t\t# assign data\n')
    # count fc layer idx
    fc_idx = []
    count = 0
    for layer in data['layers']:
        if layer == 'FL':
            count += 1
        fc_idx.append(count) 
    # print(fc_idx)
    for block_idx in range(total_block_num+1):
        if block_idx != total_block_num:
            begin = int(layer_key[block_idx].split(',')[0])
            end = int(layer_key[block_idx].split(',')[1])
        elif block_idx == total_block_num:
            begin = int(layer_key[block_idx-1].split(',')[0])
            end = int(layer_key[block_idx-1].split(',')[1])
        if block_idx == 0:
            f.write('\t\t\tif block_id == %d:\n' % (block_idx))
        else:
            f.write('\t\t\telif block_id == %d:\n' % (block_idx))

        if block_idx != total_block_num:
            for device_idx in range(total_device_num):
                if device_idx == 0:
                    f.write('\t\t\t\tif idx == %d:\n' % (device_idx))
                else:
                    f.write('\t\t\t\telif idx == %d:\n' % (device_idx))
                if data['layers'][begin] == 'conv':
                    f.write('\t\t\t\t\ty = x[:, :, %d:%d, :]\n' 
                        % (data['devices'][device_idx][layer_key[block_idx]][0], data['devices'][device_idx][layer_key[block_idx]][1]+1))
                elif data['layers'][begin] == 'FL':
                    f.write('\t\t\t\t\ty = relu(x + net.fc%d.bias.detach().numpy())\n' 
                        % (fc_idx[begin]))
        elif block_idx == total_block_num:
            if data['layers'][end] == 'conv' or data['layers'][end] == 'pool':
                f.write('\t\t\t\ty = x\n')
            elif data['layers'][end] == 'FL':
                 f.write('\t\t\t\ty = x + net.fc%d.bias.detach().numpy()\n' % fc_idx[end])
            f.write('\t\t\t\tbreak\n')
    f.write('\t\t\t# print(\'to\', idx, y.shape)\n')
    f.write('\t\t\tsendall(conn, pickle.dumps({\n')
    f.write('\t\t\t\t\'key\': \'data\',\n')
    f.write('\t\t\t\t\'data\': y\n')
    f.write('\t\t\t}))\n')
    f.write('\tconn.close()\n\n')

def write_softmax():
    f.write('def softmax(x):\n')
    f.write('\treturn np.exp(x) / np.sum(np.exp(x), axis=0)\n\n')

def write_socket():
    f.write('with socket(AF_INET, SOCK_STREAM) as s:\n')
    f.write('\ttry:\n')
    f.write('\t\ts.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)\n')
    f.write('\t\ts.bind((HOST, PORT))\n')
    f.write('\t\ts.listen()\n')
    f.write('\t\tcondition = threading.Condition()\n')
    f.write('\t\tfor i in range(device_num):\n')
    f.write('\t\t\tconn, addr = s.accept()\n')
    f.write('\t\t\t# print(\'a device connect\')\n')
    f.write('\t\t\tt = threading.Thread(\n')
    f.write('\t\t\t\ttarget = job,\n')
    f.write('\t\t\t\targs = (conn, condition)\n')
    f.write('\t\t\t)\n')
    f.write('\t\t\tt.start()\n')
    f.write('\t\tfor i in range(device_num):\n')
    f.write('\t\t\tt.join()\n')
    f.write('\t\t# print(y[:50])\n')
    f.write('\t\t# print(y.view(-1).detach().numpy()[:50])\n')
    f.write('\t\ty = softmax(y)\n')
    f.write('\t\tindex = np.argmax(y)\n')
    f.write('\t\tprint(index)\n')
    f.write('\texcept error:\n')
    f.write('\t\ts.close()\n')

if not os.path.exists('codegen'):
    os.mkdir('codegen')

for model in range(4):
    with open('data/prefetch'+str(model)+'.json') as f:
        data = json.loads(f.read())

    # print(data)
    total_device_num = len(data['devices'])
    total_block_num  = len(data['devices'][0].keys())
    

    path = {
        0: 'yolov2',
        1: 'alexnet_tmp',
        2: 'vgg16',
        3: 'vgg19',
    }.get(model)
    if not os.path.exists('codegen/'+path):
        os.mkdir('codegen/'+path)
    with open('codegen/'+path+'/server.py', 'w') as f:
        write_header()

        f.write('pcnn_path = str(Path(__file__).parent.parent.parent.absolute())\n\n')
        f.write('image_path = sys.argv[4]\n')
        f.write('image = Image.open(image_path)\n')
        f.write('image = image.resize((224, 224), Image.ANTIALIAS)\n')
        f.write('# convert image to numpy array\n')
        f.write('x = np.array([np.asarray(image)[:, :, :3]])\n')
        f.write('x = torch.Tensor(list(x)).permute(0, 3, 2, 1)\n\n\n')
        f.write('y = None\n')
        f.write('cnt = 0\n')
        f.write('offset = 0\n\n')

        write_relu()
        write_net()

        f.write('net = Net()\n')
        f.write('net.load_state_dict(torch.load(os.path.join(pcnn_path, \'models\', \'alexnet\')))\n\n')

        write_recvall()
        write_recv()
        write_sendall()
        write_job()
        write_softmax()
        write_socket()

            