"""
Declarative classes for characters go here.
Use strings (be wary of typos!!!) to declare relationships (a.k.a. a characters' current location)
Remember that you can set the value directly to the table without using the reverse accessor/manager. For
example Character.location_name is the table while Character.location is just a relationship object to
manage the relationship between tables.
The name of the class is irrelevant.

Defaults:
    energy = 2000
"""
from gensim.serializers import GenericLocation, GenericPath, GenericCharacter
