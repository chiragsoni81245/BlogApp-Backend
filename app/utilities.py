

def get_error_messages(error):
	error_msg = []
	for error_info in error.errors():
		if error_info["type"] == "value_error.missing":
			attribute =(" ".join(error_info["loc"][0].split("_"))).title()
			error_msg.append(attribute +" is required")
		elif error_info["type"] == "value_error.str.regex":
			error_msg.append("Invalid Format")
		else:
			if error_info["loc"][0].lower() not in error_info["msg"].lower():
				msg = "{} {}".format(error_info["loc"][0], error_info["msg"])
			else:
				msg = error_info["msg"]
			msg = msg[0].upper() + msg[1:]
			error_msg.append(msg)
	return error_msg