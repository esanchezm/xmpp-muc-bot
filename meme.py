#!/usr/bin/env python
import sys, re
from pyquery import PyQuery

memes = {
    'fry'          : { 'generatorID': 305,   'imageID' : 84688 },
    'raptor'       : { 'generatorID': 17,    'imageID' : 984 },
    'toad'         : { 'generatorID': 3,     'imageID' : 203 },
    'foreveralone' : { 'generatorID': 116,   'imageID' : 142442 },
    'yuno'         : { 'generatorID': 2,     'imageID' : 166088 },
    'penguin'      : { 'generatorID': 29,    'imageID' : 983 },
    'pedobear'     : { 'generatorID': 235,   'imageID' : 564288 },
    'trollface'    : { 'generatorID': 26298, 'imageID' : 1182094 },
    'yaoming'      : { 'generatorID': 1610,  'imageID' : 458071 },
    'kid'          : { 'generatorID': 121,   'imageID' : 1031 },
    'yodawg'       : { 'generatorID': 79,    'imageID' : 108785 }
    }

GENURL = 'http://memegenerator.net/create/instance'
def create_meme(meme, t0, t1):
    data = {
       'languageCode': 'es',
       'text0': t0,
       'text1': t1
    }

    if not meme in memes:
        return 'Not Found'
    
    data = dict(data.items() + memes[meme].items())
    
    try:
        pq = PyQuery(url=GENURL, data=data, method='post')
    except Exception, e:
        return 'Error %s' % e
    s = str(pq)
    # <img src="http://d.images.memegenerator.net/instances/400x/xxxxxx.jpg
    regex = re.compile("http://\w.images.memegenerator.net/instances/400x/\d+.jpg")
    match = regex.search(s)
    if match is None:
        return 'Error'
    else:
        return match.group(0)

def list_memes():
    l = []
    list = ''
    for m in memes:
        l.append(m)
    l.sort()
    for i in l:
        list += i + ', '
    return list[:-2]

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('Usage meme text0 text1')
        sys.exit(1)
    print create_meme(sys.argv[1], sys.argv[2], sys.argv[3])
