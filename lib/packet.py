#!/usr/bin/env python
# coding:utf-8

"""

    Message format defination and serializer that support class inheritence.

    
    class AsyncMsg(PacketBase):
        pass

    AsyncMsg.clsinit()
    AsyncMsg.add_check_attr('to')
    AsyncMsg.add_attr('from')

    class TaskMsg(AsyncMsg): # inherit attribute from AsyncMsg

        @classmethod
        def _check(cls, data):
            PacketBase._check(data)
            # do your checking
        
    TaskMsg.clsinit()
    TaskMsg.add_check_attr('task_id', 'host')
    TaskMsg.add_attr('start_time')
    PacketBase.register_type(TaskMsg)
    use_json()   # use json as serializer
    
    m = TaskMsg()
    m.task_id = 1
    m.host = 'host1'
    m.to = 'master'
    # or
    # m = TaskMsg(task_id=1, host='host1', to='master')
    buf = m.serialize()
    m2 = PacketBase.deserialize(buf)
    print m2.host

# @author frostyplanet@gmail.com
# 2013-07-08

"""



import time


class PacketDataError(Exception):

    """ error found during serializing / deserializing """

    def __init__(self, *args):
        Exception.__init__(self, *args)


class PacketBase(object):
    cls_dict = {}
    _meta_attrs = ['type', 'data', 'c_ts']
    _attrs = set()
    _check_attrs = set()
    _meta_data = None
    _serializer = None
    _deserialzer = None

    def __init__(self, init=True, **kargs):
        if init:
            self._meta_data = {
                "type": self.__class__.__name__,
                "data": {},
                "c_ts": time.time(),
                }
            for k, v in kargs.items():
                self.set(k, v)

    def clsinit(cls):
        """ initialize a new packet type """
        base = cls.__base__
        cls._attrs = set(base._attrs)
        cls._check_attrs = set(base._check_attrs)
    clsinit = classmethod(clsinit)


    def add_attr(cls, *args):
        """ add attribute to packet that can be absent """
        for name in args:
            if name in cls._meta_attrs:
                raise AttributeError("attribute name %s is reserved" % (name))
            if name not in cls._attrs:
                cls._attrs.add(name)
    add_attr = classmethod(add_attr)

    def add_check_attr(cls, *args):
        """ add attribute to packet that must be not null """
        for name in args:
            if name in cls._meta_attrs:
                raise AttributeError("attribute name %s is reserved" % (name))
            if name not in cls._check_attrs:
                cls._check_attrs.add(name)
            if name not in cls._attrs:
                cls._attrs.add(name)
    add_check_attr = classmethod(add_check_attr)



    @property
    def data(self):
        return self._meta_data["data"]

    def register_type(cls, *args):
        """ register the packet type so its object can be deserialized """
        for c in args:
            cls.cls_dict[c.__name__] = c
    register_type = classmethod(register_type)

    def unregister_type(cls, *args):
        for c in args:
            del cls.cls_dict[c.__name__]
    unregister_type = classmethod(unregister_type)


    def _check(cls, data):
        """ you can inherit this method to do checking """
        _data = data['data']
        for i in cls._check_attrs:
            if not _data.has_key(i) or _data.get(i) is None:
                raise PacketDataError("key %s of %s not found or is None" % (i, cls.__name__))
    _check = classmethod(_check)

    def deserialize(cls, sdata, expect_cls=None):
        data = None
        try:
            data = cls._deserialzer(sdata)
        except Exception, e:
            raise PacketDataError("cannot deserialize, %s" % (str(e)))
        for i in cls._meta_attrs:
            if not data.has_key(i):
                raise PacketDataError("key %s not found, data invalid" % (i))
        class_name = data['type']
        _clsobj = None
        if class_name:
            _clsobj = cls.cls_dict.get(class_name)
        if _clsobj is None:
            print cls, cls.cls_dict
            raise PacketDataError("type %s not regconized" % (class_name))
        if expect_cls and _clsobj != expect_cls:
            raise PacketDataError("expect %s, but got %s" % (expect_cls.__name__, class_name))
        _clsobj._check(data)

        obj = _clsobj(init=False)
        obj._meta_data = data
        obj._post_deserialize()
        return obj
    deserialize = classmethod(deserialize)


    def _post_deserialize(self):
        """ which is executed after deserialize
        """
        pass


    def serialize(self):
        self._check(self._meta_data)
        try:
            msg_buf =  self._serializer(self._meta_data)
            return msg_buf
        except Exception, e:
            raise PacketDataError("cannot serialize, %s" % (str(e)))



    def __getattr__(self, name):
        if name in self._meta_attrs:
            return self._meta_data[name]
        if name in self._attrs:
            return self._meta_data['data'].get(name)
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        if name in self._attrs:
            self._meta_data['data'][name] = value
            return value
        elif name in ['_meta_data', '_attrs', '_check_attrs']:
            self.__dict__[name] = value
        else:
            raise AttributeError("setting unknown attr %s" % (name))

    def set(self, name, value):
        if name not in self._attrs:
            raise AttributeError("setting unknown attr %s" % (name))
        self._meta_data['data'][name] = value
        return value

    def __str__(self):
        msg = "%s[%s" % (self._meta_data["type"], self.get_time())
        data = self._meta_data["data"]
        for a in self._attrs:
            msg += ",%s:%s" % (a, str(data.get(a)))
        msg += "]"
        return msg

    def short_str(self):
        msg = "%s[%s]" % (self._meta_data["type"], self.get_time())
        return msg

    def get_time(self, ts=None):
        if ts == None:
            ts = self._meta_data["c_ts"]
        return time.strftime("%H:%M:%S", time.localtime(ts))


def deserialize(buf, expect_cls=None):
    return PacketBase.deserialize(buf, expect_cls)


def use_json():
    import json
    PacketBase._serializer = staticmethod(json.dumps)
    PacketBase._deserialzer = staticmethod(json.loads)

def use_pickle():
    import pickle
    PacketBase._serializer = staticmethod(pickle.dumps)
    PacketBase._deserialzer = staticmethod(pickle.loads)

use_pickle()


def detect_type_and_register(global_dict):
    """ global_dict need to be globals() in the top level """
    type_list = global_dict.values()
    import types
    for _obj in type_list:
        if isinstance(_obj, (types.ClassType, types.TypeType)): # old style and new style class
            if  issubclass(_obj, PacketBase) and _obj.__name__ != PacketBase.__name__:
                PacketBase.register_type(_obj)



####################### test #######################

import unittest

class TestPacketBasic(unittest.TestCase):


    class P1(PacketBase):
        pass

    def setUp(self):
        self.P1.clsinit()
        PacketBase.register_type(self.P1)

    def tearDown(self):
        PacketBase.unregister_type(self.P1)


    def test_reserved_attr(self):
        try:
            self.P1.add_attr('type')
            raise Exception("missing reserved keyword check")
        except Exception, e:
            print "[expected error]", e

    def test_get_invalid(self):
        p = self.P1()
        self.P1.add_attr("aaa")
        try:
            print p.name1
            raise Exception("should raise exception")
        except AttributeError, e:
            print "[expected error]", e

    def test_set_invalid(self):
        p = self.P1()
        self.P1.add_attr("aaa")
        try:
            p.name1 = 'test'
            raise Exception("should raise exception")
        except AttributeError, e:
            print "[expected error]", e



    def _test_one(self, cls, arr):
        i = 0
        check_dict =  {}
        for i in arr:
            check_dict[i] = i + 'haha'
        obj = cls()
        for k, v in check_dict.iteritems():
            setattr(obj, k, v)
        print "test", cls.__name__, obj
        #print "serialize"
        data = obj.serialize()
        #print "deserialize"
        obj2 = PacketBase.deserialize(data)
        self.assertEqual(obj2.__class__, cls)
        self.assertEqual(obj2._meta_data, obj._meta_data)
        for k, v in check_dict.iteritems():
            self.assertEqual(getattr(obj2, k), v)
        return obj2

    def test2(self):
        self.P1.add_check_attr('name1', 'name2')
        self.P1.add_attr('name3', 'name4')
        p = self.P1()
        self._test_one(self.P1, ['name1', 'name2'])
        self._test_one(self.P1, ['name1', 'name2', 'name3', 'name4'])

    def test1(self):
        self.P1.add_attr('name1')
        p = self.P1()
        p.name1 = 1
        self.assertEqual(p.name1, 1)
        data = p.serialize()
        _p = PacketBase.deserialize(data)
        self.assertEqual(_p.name1, 1)
        print _p.get_time()

    
    def test_serialize_missing(self):
        self.P1.add_check_attr('name1', 'name2')
        self.P1.add_attr('name3', 'name4')
        p = self.P1()
        p.name1 = 1
        p.name3 = 3
        try:
            p.serialize()
            raise Exception("missing check")
        except Exception, e:
            print "[expected error]", e

class TestPacketMultiple(unittest.TestCase):

    def test_multi(self):
        class P2(PacketBase):
            pass 
        P2.clsinit()
        P2.add_attr("name1")
        self.assert_('name1' in P2._attrs)

        class P3(PacketBase):
            pass
        P3.clsinit()
        self.assert_('name1' not in P3._attrs)
        P3.add_attr("name1")
        self.assert_('name1' in P3._attrs)

        class P4(P2):
            pass
        P4.clsinit()
        P4.add_attr('name2')
        self.assert_('name1' in P4._attrs)
        self.assert_('name2' in P4._attrs)


if __name__ == '__main__':
    unittest.main()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
