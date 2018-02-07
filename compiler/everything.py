# import everything because I feel like it
# pylint: disable=unused-wildcard-import, wildcard-import

from compiler.objects.astnode import *
from compiler.objects.base import *
from compiler.objects.builder import *
from compiler.objects.errors import *
from compiler.objects.ir_object import *
from compiler.objects.literals import *
from compiler.objects.operations import *
from compiler.objects.statements import *
from compiler.objects.types import *
from compiler.backend.rustvm.codegen import *
from compiler.backend.rustvm.encoder import *
from compiler.backend.rustvm.register_allocate import *
from compiler.parser import *
