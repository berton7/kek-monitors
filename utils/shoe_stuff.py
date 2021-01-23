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

	@property
	def link(self):
		return self.__link

	@link.setter
	def link(self, link):
		if not isinstance(link, str):
			raise Exception("Link is not a string")
		self.__link = link

	@property
	def img_link(self):
		return self.__img_link

	@img_link.setter
	def img_link(self, img_link):
		if not isinstance(img_link, str):
			raise Exception("Img_link is not a string")
		self.__img_link = img_link

	@property
	def name(self):
		return self.__name

	@name.setter
	def name(self, name):
		if not isinstance(name, str):
			raise Exception("Name is not a string")
		self.__name = name

	@property
	def style_code(self):
		return self.__style_code

	@style_code.setter
	def style_code(self, style_code):
		if not isinstance(style_code, str):
			raise Exception("Style_code is not a string")
		self.__style_code = style_code

	@property
	def price(self):
		return self.__price

	@price.setter
	def price(self, price):
		if not isinstance(price, str):
			raise Exception("Price is not a string")
		self.__price = price

	@property
	def sizes(self):
		return self.__sizes

	@sizes.setter
	def sizes(self, sizes):
		if not isinstance(sizes, dict):
			raise Exception("Sizes is not a dict")
		self.__sizes = sizes

	@property
	def in_stock(self):
		return self.__in_stock

	@in_stock.setter
	def in_stock(self, in_stock):
		if not isinstance(in_stock, bool):
			raise Exception("In_stock is not a bool")
		self.__in_stock = in_stock

	@property
	def out_of_stock(self):
		return self.__out_of_stock

	@out_of_stock.setter
	def out_of_stock(self, out_of_stock):
		if not isinstance(out_of_stock, bool):
			raise Exception("Out_of_stock is not a bool")
		self.__out_of_stock = out_of_stock

	@property
	def back_in_stock(self):
		return self.__back_in_stock

	@back_in_stock.setter
	def back_in_stock(self, back_in_stock):
		if not isinstance(back_in_stock, bool):
			raise Exception("Back_in_stock is not a bool")
		self.__back_in_stock = back_in_stock

	@property
	def release_date(self):
		return self.__release_date

	@release_date.setter
	def release_date(self, release_date):
		if not isinstance(release_date, str):
			raise Exception("Release_date is not a string")
		self.__release_date = release_date

	@property
	def release_method(self):
		return self.__release_method

	@release_method.setter
	def release_method(self, release_method):
		if not isinstance(release_method, str):
			raise Exception("Release_method is not a string")
		self.__release_method = release_method

	@property
	def reason(self):
		return self.__reason

	@reason.setter
	def reason(self, reason):
		if not isinstance(reason, int):
			raise Exception("Reason is not an int")
		if reason != OTHER and reason != NEW_RELEASE and reason != RESTOCK and reason != INCOMING:
			raise Exception("Invalid reason provided")
		self.__reason = reason
