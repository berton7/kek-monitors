from utils.server.msg import *
import pickle
r = badResponse()
br = pickle.loads(r.get_bytes())
print(r.__dict__)
print(br)
