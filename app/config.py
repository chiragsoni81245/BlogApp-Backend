import os


class app_config():

    if os.environ.get("ENVIRONMENT"):
        ACCESS_TOKEN_EXPIRY_TIME = 180
        ACCESS_TOKEN_SECRET_KEY = '1sxfcghjkmjiuihjv2wsdgfh09ij23456789ihfcxzaq2346ujnbvcxzswe456324567890poiuhgfdcszxcvbjkl.,mnbvcxs'
        REFRESH_TOKEN_EXPIRY_TIME = 36000
        REFRESH_TOKEN_SECRET_KEY = 'h098765ewqazsxvbj98trewwsc0oiuhgfvewdgpigheew3ertui09876543wqaZxvjmk nbcfdesryuijkn bvcxsdertyuhjb'
        CLIENTS:list = [ 'Application' ]
        TOKEN_CODE_EXPIRY_TIME = 120
        REST_PASSWORD_TOKEN_EXPIRY_TIME = 300
        TOKEN_CODE_SECRET_KEY = 'setrdthfgkjhn bcvxset45r678347y7ert89plmnbvcer678iol,m xzser678iknbvcdrt6789olm vcxsder56789oiuyreszkj'
        REST_PASSWORD_TOKEN_SECRET_KEY = 'setrdthfdsfbhsdfbnsdfndfn678347y7ert89plmnbvcer678iol,m xzser678iknbvcdrt6789olm vcxsder56789oiuyreszkj'
        
        EMAIL = "testemailservice22@gmail.com"
        PASSWORD = "test101@ajay"
        MAIL_SERVER = 'smtp.gmail.com'

        if os.environ.get("ENVIRONMENT")=="Development":
            SECRET_KEY = '23ertyhjko0987ytfdsew5tyu890ik cxdsertyujkuytfddftyuhb mkdfgyhujjhgfdxdfvbhjkml,kojhygfc'
            SQLALCHEMY_DATABASE_URL = os.environ.get("SQLALCHEMY_DATABASE_URL") or "postgresql://admin:Awakinn008@localhost:5432/blog_app"
        elif os.environ.get("ENVIRONMENT")=="Testing":
            SECRET_KEY = '23ertyhjko0987ytfdsew5tyu890ik cxdsertyujkuytfddftyuhb mkdfgyhujjhgfdxdfvbhjkml,kojhygfc'
            SQLALCHEMY_DATABASE_URL = "postgresql://admin:Awakinn008@localhost:5432/test_blog_app"
            TEST_ROOT_DIRECTORY = os.getcwd()
        else:
            print("Invalid Value of ENVIRONMENT in environment vriables")
            exit()
    else:
        print("Plase set ENVIRONMENT in environment variables")
        exit()