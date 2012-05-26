import os
import sys
import unittest
import httplib
import traceback

sys.path = [ os.path.join( os.path.dirname( __file__ ), "..", "src" ) ] + sys.path
import github

class FakeHttpResponse:
    def __init__( self, status, headers, output ):
        self.status = status
        self.__headers = headers
        self.__output = output

    def getheaders( self ):
        return self.__headers

    def read( self ):
        return self.__output

def fixAuthorizationHeader( headers ):
    if "Authorization" in headers:
        if headers[ "Authorization" ].startswith( "token " ):
            headers[ "Authorization" ] = "token private_token_removed"
        elif headers[ "Authorization" ].startswith( "Basic " ):
            headers[ "Authorization" ] = "Basic login_and_password_removed"
        else:
            del headers[ "Authorization" ] # Do not let sensitive info in git :-p

class RecordingHttpsConnection:
    __realHttpsConnection = httplib.HTTPSConnection

    def __init__( self, file, *args, **kwds ):
        self.__file = file
        self.__cnx = self.__realHttpsConnection( *args, **kwds )

    def request( self, verb, url, input, headers ):
        print verb, url,
        self.__cnx.request( verb, url, input, headers )
        fixAuthorizationHeader( headers )
        self.__file.write( verb + " " + url + " " + str( headers ) + " " + input + "\n" )

    def getresponse( self ):
        res = self.__cnx.getresponse()

        status = res.status
        print "=>", status
        headers = res.getheaders()
        output = res.read()

        self.__file.write( str( status ) + "\n" )
        self.__file.write( str( headers ) + "\n" )
        self.__file.write( str( output ) + "\n" )

        return FakeHttpResponse( status, headers, output )

    def close( self ):
        self.__file.write( "\n" )
        return self.__cnx.close()

class ReplayingHttpsConnection:
    def __init__( self, testCase, file ):
        self.__testCase = testCase
        self.__file = file

    def request( self, verb, url, input, headers ):
        fixAuthorizationHeader( headers )
        expectation = self.__file.readline().strip()
        self.__testCase.assertEqual( verb + " " + url + " " + str( headers ) + " " + input, expectation )

    def getresponse( self ):
        status = int( self.__file.readline().strip() )
        headers = eval( self.__file.readline().strip() )
        output = self.__file.readline().strip()

        return FakeHttpResponse( status, headers, output )

    def close( self ):
        self.__file.readline()

class BasicTestCase( unittest.TestCase ):
    recordMode = False

    def setUp( self ):
        unittest.TestCase.setUp( self )
        self.__fileName = ""
        self.__file = None
        if self.recordMode:
            httplib.HTTPSConnection = lambda *args, **kwds: RecordingHttpsConnection( self.__openFile( "w" ), *args, **kwds )
            import GithubCredentials
            self.login = GithubCredentials.login
            self.password = GithubCredentials.password
        else:
            httplib.HTTPSConnection = lambda *args, **kwds: ReplayingHttpsConnection( self, self.__openFile( "r" ) )
            self.login = "login"
            self.password = "password"

    def tearDown( self ):
        unittest.TestCase.tearDown( self )
        self.__closeReplayFileIfNeeded()

    def __openFile( self, mode ):
        for ( _, _, functionName, _ ) in traceback.extract_stack():
            if functionName.startswith( "test" ) and functionName != "test" or functionName == "setUp" or functionName == "tearDown":
                fileName = os.path.join( os.path.dirname( __file__ ), "ReplayData", self.__class__.__name__ + "." + functionName + ".txt" )
        if fileName != self.__fileName:
            self.__closeReplayFileIfNeeded()
            self.__fileName = fileName
            self.__file = open( self.__fileName, mode )
        return self.__file

    def __closeReplayFileIfNeeded( self ):
        if self.__file is not None:
            if not self.recordMode:
                self.assertEqual( self.__file.readline(), "" )
            self.__file.close()

class TestCase( BasicTestCase ):
    def setUp( self ):
        BasicTestCase.setUp( self )
        self.g = github.Github( self.login, self.password )

class TestCaseWithRepo( TestCase ):
    def setUp( self ):
        TestCase.setUp( self )
        self.repo = self.g.get_user().get_repo( "PyGithub" )

def main():
    if "--record" in sys.argv:
        BasicTestCase.recordMode = True

    unittest.main( argv = [ arg for arg in sys.argv if arg != "--record" ] )
