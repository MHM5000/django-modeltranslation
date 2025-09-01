"""
Tests for django-polymorphic integration with django-modeltranslation.
"""

from django.test import TestCase
from django.db import models

try:
    from polymorphic.models import PolymorphicModel
    POLYMORPHIC_AVAILABLE = True
except ImportError:
    POLYMORPHIC_AVAILABLE = False
    # Create a dummy PolymorphicModel for when polymorphic is not installed
    class PolymorphicModel(models.Model):
        class Meta:
            abstract = True

from modeltranslation.translator import translator, TranslationOptions, NotRegistered


class PolymorphicIntegrationTest(TestCase):
    """
    Test that django-modeltranslation works correctly with django-polymorphic models.
    """

    def setUp(self):
        # Clear translator registry for clean tests
        translator._registry.clear()

    def test_polymorphic_parent_accessible_after_child_registration(self):
        """
        Test that registering a polymorphic child model makes the parent model
        accessible through get_options_for_model (marked as related).
        """
        if not POLYMORPHIC_AVAILABLE:
            self.skipTest("django-polymorphic not available")

        # Define polymorphic models
        class Animal(PolymorphicModel):
            name = models.CharField(max_length=100)
            
            class Meta:
                app_label = 'test_polymorphic'

        class Dog(Animal):
            breed = models.CharField(max_length=100)
            
            class Meta:
                app_label = 'test_polymorphic'

        # Register only the child model
        class DogTranslationOptions(TranslationOptions):
            fields = ('breed',)

        translator.register(Dog, DogTranslationOptions)

        # Child model should work normally
        dog_opts = translator.get_options_for_model(Dog)
        self.assertTrue(dog_opts.registered)
        self.assertEqual(list(dog_opts.local_fields.keys()), ['breed'])

        # Parent model should be accessible (marked as related)
        animal_opts = translator.get_options_for_model(Animal)
        self.assertFalse(animal_opts.registered)
        self.assertTrue(animal_opts.related)

    def test_multiple_polymorphic_inheritance_levels(self):
        """
        Test that multiple levels of polymorphic inheritance work correctly.
        """
        if not POLYMORPHIC_AVAILABLE:
            self.skipTest("django-polymorphic not available")

        # Define multi-level polymorphic models
        class Animal(PolymorphicModel):
            name = models.CharField(max_length=100)
            
            class Meta:
                app_label = 'test_polymorphic'

        class Mammal(Animal):
            fur_color = models.CharField(max_length=50)
            
            class Meta:
                app_label = 'test_polymorphic'

        class Dog(Mammal):
            breed = models.CharField(max_length=100)
            
            class Meta:
                app_label = 'test_polymorphic'

        # Register only the leaf model
        class DogTranslationOptions(TranslationOptions):
            fields = ('breed',)

        translator.register(Dog, DogTranslationOptions)

        # All levels should be accessible
        dog_opts = translator.get_options_for_model(Dog)
        self.assertTrue(dog_opts.registered)

        mammal_opts = translator.get_options_for_model(Mammal)
        self.assertFalse(mammal_opts.registered)
        self.assertTrue(mammal_opts.related)

        animal_opts = translator.get_options_for_model(Animal)
        self.assertFalse(animal_opts.registered)
        self.assertTrue(animal_opts.related)

    def test_abstract_models_still_fail(self):
        """
        Test that abstract models (including PolymorphicModel itself) still
        correctly raise NotRegistered exceptions.
        """
        if not POLYMORPHIC_AVAILABLE:
            self.skipTest("django-polymorphic not available")

        class Animal(PolymorphicModel):
            name = models.CharField(max_length=100)
            
            class Meta:
                app_label = 'test_polymorphic'

        class Dog(Animal):
            breed = models.CharField(max_length=100)
            
            class Meta:
                app_label = 'test_polymorphic'

        class DogTranslationOptions(TranslationOptions):
            fields = ('breed',)

        translator.register(Dog, DogTranslationOptions)

        # PolymorphicModel should still fail (it's abstract)
        with self.assertRaises(NotRegistered):
            translator.get_options_for_model(PolymorphicModel)

    def test_regular_inheritance_still_works(self):
        """
        Test that regular multi-table inheritance (non-polymorphic) still works
        after the polymorphic fix.
        """
        class Parent(models.Model):
            parent_field = models.CharField(max_length=100)
            
            class Meta:
                app_label = 'test_regular'

        class Child(Parent):
            child_field = models.CharField(max_length=100)
            
            class Meta:
                app_label = 'test_regular'

        class ChildTranslationOptions(TranslationOptions):
            fields = ('child_field',)

        translator.register(Child, ChildTranslationOptions)

        # Child should work
        child_opts = translator.get_options_for_model(Child)
        self.assertTrue(child_opts.registered)

        # Parent should be accessible (marked as related)
        parent_opts = translator.get_options_for_model(Parent)
        self.assertFalse(parent_opts.registered)
        self.assertTrue(parent_opts.related)

    def test_abstract_inheritance_unchanged(self):
        """
        Test that abstract inheritance behavior is unchanged - abstract models
        should still raise NotRegistered.
        """
        class AbstractParent(models.Model):
            abstract_field = models.CharField(max_length=100)
            
            class Meta:
                abstract = True
                app_label = 'test_abstract'

        class ConcreteChild(AbstractParent):
            concrete_field = models.CharField(max_length=100)
            
            class Meta:
                app_label = 'test_abstract'

        class ConcreteChildTranslationOptions(TranslationOptions):
            fields = ('concrete_field',)

        translator.register(ConcreteChild, ConcreteChildTranslationOptions)

        # Child should work
        child_opts = translator.get_options_for_model(ConcreteChild)
        self.assertTrue(child_opts.registered)

        # Abstract parent should still fail
        with self.assertRaises(NotRegistered):
            translator.get_options_for_model(AbstractParent)