"""
# How declarative classes work
The startup functions @ gensim.management.db will pass the client with an
active connection to the database during runtime to create all the necessary data
if and only if the class inerits from gensim.serializers.Serializer and its _is_data attribute
is set to True.

# How the serialization API works
Check gensim.serializers for details of how every specific serializer works.
but in short:
    1. The serializer maps 1:1 columns to attributes as long as they are not primary keys
    (relationship between models)
    2. Related fields usually require some special handling to be easy do declare here but
    often you just have to create them declaratively (dont set the is_data attribute to True for these!!!)
    and add it to an array
    For example:
    class SomeLocation(GenericLocation):
        name = "name"

    class Somecharacter(GenericCharacter):
        home = SomeLocation
        _is_data = True

    class SomeArea(GenericArea):
        locations = [SomeLocation]
        _is_data = True
"""
