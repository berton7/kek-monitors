OTHER = 0
NEW_RELEASE = 1
RESTOCK = 2
INCOMING = 3


class Shoe:
	def __init__(self):
		self.link = ""
		self.img_link = ""
		self.name = ""
		self.style_code = ""
		self.price = "Not available"
		self.sizes = {}
		# self.sizes = {
		# 	"size": {
		#		"available": True, # only required key
		# 		"atc": "link",
		# 		"quick_tasks": {
		# 			"name1": "link1",
		# 			"name2": "link2"
		# 		},
		#		"other": [
		# 			{
		#				name: "name",
		#				link: "link"
		# 			},
		# 			{
		#				name: "name",
		#				link: "link"
		# 			}
		# 		]
		# 	}
		# }
		self.in_stock = False
		self.release_date = ""
		self.back_in_stock = False
		self.out_of_stock = False
		self.release_method = ""
		self.reason = OTHER
		self.tags = {}
		self.other = {}
