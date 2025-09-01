"""
Tests for admin loading order fix with polymorphic models.
"""

from django.test import TestCase
from django.db import models
from django.contrib import admin

try:
    from polymorphic.models import PolymorphicModel
    from polymorphic.admin import PolymorphicChildModelAdmin
    POLYMORPHIC_AVAILABLE = True
except ImportError:
    POLYMORPHIC_AVAILABLE = False
    # Create a dummy PolymorphicModel for when polymorphic is not installed
    class PolymorphicModel(models.Model):
        class Meta:
            abstract = True
    
    class PolymorphicChildModelAdmin:
        pass

from modeltranslation.admin import TabbedTranslationAdmin
from modeltranslation.translator import translator, TranslationOptions, NotRegistered


class AdminLoadingOrderTest(TestCase):
    """
    Test that admin classes can be created before translation registration.
    This fixes the issue where django-polymorphic admin classes would fail
    during Django app loading due to translation registration happening later.
    """

    def setUp(self):
        # Clear translator registry for clean tests
        translator._registry.clear()

    def test_admin_creation_before_translation_registration(self):
        """
        Test that TabbedTranslationAdmin can be created before translation registration.
        This is the key test - ensuring no NotRegistered exception is raised.
        """
        if not POLYMORPHIC_AVAILABLE:
            self.skipTest("django-polymorphic not available")

        # Use existing models from the test app to avoid Django model creation issues
        from modeltranslation.tests.models import TestModel
        from polymorphic.models import PolymorphicModel

        # Create a simple polymorphic model hierarchy
        class TestVehicle(PolymorphicModel):
            name = models.CharField(max_length=100)
            
            class Meta:
                app_label = 'test_admin_loading'

        class TestCar(TestVehicle):
            brand = models.CharField(max_length=100)
            
            class Meta:
                app_label = 'test_admin_loading'

        # Create admin BEFORE translation registration (this should work now)
        class TestCarAdmin(TabbedTranslationAdmin, PolymorphicChildModelAdmin):
            base_model = TestVehicle

        # This should succeed with the fix - no NotRegistered exception
        try:
            admin_instance = TestCarAdmin(TestCar, admin.site)
            admin_created = True
        except NotRegistered:
            admin_created = False
        
        self.assertTrue(admin_created, "Admin creation should not raise NotRegistered")
        
        # Verify the admin is in deferred state
        self.assertTrue(admin_instance._translation_deferred)
        self.assertIsNone(admin_instance.trans_opts)

        # Now register translations
        class TestCarTranslationOptions(TranslationOptions):
            fields = ('brand',)

        translator.register(TestCar, TestCarTranslationOptions)

        # Trigger the deferred initialization
        admin_instance._ensure_translation_setup()
        
        # Verify the admin is now properly initialized
        self.assertFalse(admin_instance._translation_deferred)
        self.assertIsNotNone(admin_instance.trans_opts)
        self.assertTrue(admin_instance.trans_opts.registered)

    def test_normal_admin_registration_still_works(self):
        """
        Test that the normal workflow (translation first, then admin) still works.
        """
        # Define model
        class Book(models.Model):
            title = models.CharField(max_length=100)
            
            class Meta:
                app_label = 'test_normal_workflow'

        # Register translation first (normal workflow)
        class BookTranslationOptions(TranslationOptions):
            fields = ('title',)

        translator.register(Book, BookTranslationOptions)

        # Create admin after translation registration
        class BookAdmin(TabbedTranslationAdmin):
            pass

        admin_instance = BookAdmin(Book, admin.site)
        
        # Verify the admin is immediately ready (not deferred)
        self.assertFalse(admin_instance._translation_deferred)
        self.assertIsNotNone(admin_instance.trans_opts)
        self.assertTrue(admin_instance.trans_opts.registered)
        self.assertEqual(list(admin_instance.trans_opts.local_fields.keys()), ['title'])

    def test_deferred_admin_methods_work_correctly(self):
        """
        Test that admin methods work correctly with deferred initialization.
        This test focuses on the defensive behavior rather than full functionality.
        """
        # Create a mock model that's not registered
        class MockModel(models.Model):
            title = models.CharField(max_length=100)
            
            class Meta:
                app_label = 'test_deferred_methods'

        class MockModelAdmin(TabbedTranslationAdmin):
            pass

        # This should work without crashing due to deferred initialization
        admin_instance = MockModelAdmin(MockModel, admin.site)
        
        # Should be deferred since model is not registered
        self.assertTrue(admin_instance._translation_deferred)
        self.assertIsNone(admin_instance.trans_opts)
        
        # These methods should handle the deferred state gracefully (no crash)
        try:
            excluded_fields = admin_instance._exclude_original_fields(['some_field'])
            self.assertEqual(excluded_fields, ('some_field',))  # No translation fields to exclude
            
            replaced_fields = admin_instance.replace_orig_field(['title'])
            self.assertEqual(replaced_fields, ['title'])  # No replacement yet
            
            # The key test - these methods don't crash when translation is not available
            methods_work = True
        except Exception:
            methods_work = False
        
        self.assertTrue(methods_work, "Admin methods should work gracefully when translation is deferred")

    def test_admin_with_no_translation_fields(self):
        """
        Test admin behavior for models that are never registered for translation.
        """
        # Define model that won't be registered for translation
        class SimpleModel(models.Model):
            name = models.CharField(max_length=100)
            
            class Meta:
                app_label = 'test_no_translation'

        # Create admin (this should work and stay in deferred state)
        class SimpleModelAdmin(TabbedTranslationAdmin):
            pass

        admin_instance = SimpleModelAdmin(SimpleModel, admin.site)
        
        # Should be in deferred state
        self.assertTrue(admin_instance._translation_deferred)
        self.assertIsNone(admin_instance.trans_opts)
        
        # Methods should work gracefully
        excluded_fields = admin_instance._exclude_original_fields()
        self.assertEqual(excluded_fields, ())
        
        replaced_fields = admin_instance.replace_orig_field(['name'])
        self.assertEqual(replaced_fields, ['name'])
        
        # Calling ensure_translation_setup should not change anything
        admin_instance._ensure_translation_setup()
        self.assertTrue(admin_instance._translation_deferred)  # Still deferred
        self.assertIsNone(admin_instance.trans_opts)  # Still None

    def test_polymorphic_parent_model_accessibility(self):
        """
        Test that polymorphic parent models are accessible after child registration.
        This verifies that both the translator fix and admin fix work together.
        """
        if not POLYMORPHIC_AVAILABLE:
            self.skipTest("django-polymorphic not available")

        # Define polymorphic models
        class Shape(PolymorphicModel):
            name = models.CharField(max_length=100)
            
            class Meta:
                app_label = 'test_polymorphic_parent'

        class Circle(Shape):
            radius = models.FloatField()
            
            class Meta:
                app_label = 'test_polymorphic_parent'

        # Create admin for child model before translation registration
        class CircleAdmin(TabbedTranslationAdmin, PolymorphicChildModelAdmin):
            base_model = Shape

        admin_instance = CircleAdmin(Circle, admin.site)
        self.assertTrue(admin_instance._translation_deferred)

        # Register only the child model
        class CircleTranslationOptions(TranslationOptions):
            fields = ('radius',)

        translator.register(Circle, CircleTranslationOptions)

        # Both child and parent should be accessible
        circle_opts = translator.get_options_for_model(Circle)
        self.assertTrue(circle_opts.registered)

        shape_opts = translator.get_options_for_model(Shape)
        self.assertFalse(shape_opts.registered)
        self.assertTrue(shape_opts.related)

        # Admin should now work correctly
        admin_instance._ensure_translation_setup()
        self.assertFalse(admin_instance._translation_deferred)
        self.assertIsNotNone(admin_instance.trans_opts)