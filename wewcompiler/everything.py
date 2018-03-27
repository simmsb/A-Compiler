# import everything because I feel like it
# pylint: disable=unused-wildcard-import, wildcard-import

from wewcompiler.objects.astnode import *
from wewcompiler.objects.base import *
from wewcompiler.objects.builder import *
from wewcompiler.objects.errors import *
from wewcompiler.objects.inlnasm import *
from wewcompiler.objects.ir_object import *
from wewcompiler.objects.literals import *
from wewcompiler.objects.operations import *
from wewcompiler.objects.statements import *
from wewcompiler.objects.types import *
from wewcompiler.objects.variable import *
from wewcompiler.backend.rustvm.assemble import *
from wewcompiler.backend.rustvm.desugar import *
from wewcompiler.backend.rustvm.encoder import *
from wewcompiler.backend.rustvm.register_allocate import *
from wewcompiler.parser import *
