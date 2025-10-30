from django.contrib import admin, messages
from django.urls import path, reverse
from django.template.response import TemplateResponse
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from django.utils.html import escape
from django.utils.http import urlencode
from django.http import HttpResponse
import csv
import io
import json
from bson import ObjectId
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None
from django.core.files.storage import default_storage
from django.conf import settings
import os
import mimetypes
from uuid import uuid4

from .models import DocumentService
from core.mongo import get_db


class LibraryAdminViews:
    """Custom admin views for managing library documents and related resources."""

    def get_urls(self):
        urls = [
            path('library/documents/', admin.site.admin_view(self.documents_list), name='library_documents'),
            path('library/documents/add/', admin.site.admin_view(self.document_create), name='library_document_add'),
            path('library/documents/export/', admin.site.admin_view(self.documents_export), name='library_documents_export'),
            path('library/documents/<str:doc_id>/', admin.site.admin_view(self.document_detail), name='library_document_detail'),
            path('library/documents/<str:doc_id>/edit/', admin.site.admin_view(self.document_edit), name='library_document_edit'),
            path('library/posts/', admin.site.admin_view(self.posts_list), name='library_posts'),
            path('library/posts/add/', admin.site.admin_view(self.post_create), name='library_post_add'),
            path('library/posts/<str:post_id>/', admin.site.admin_view(self.post_detail), name='library_post_detail'),
            path('library/posts/<str:post_id>/edit/', admin.site.admin_view(self.post_edit), name='library_post_edit'),
        ]
        return urls

    def documents_list(self, request):
        # Only allow staff users to access these views
        if not getattr(request.user, 'is_staff', False):
            raise PermissionDenied()

        db = get_db()

        # Handle bulk actions
        if request.method == 'POST':
            action = request.POST.get('action')
            ids = request.POST.getlist('selected_ids')
            if ids:
                oids = []
                for s in ids:
                    try:
                        oids.append(ObjectId(s))
                    except Exception:
                        continue
                if action == 'delete_selected':
                    res = db.documents.delete_many({'_id': {'$in': oids}})
                    messages.success(request, f'Deleted {res.deleted_count} documents')
                    return redirect('admin:library_documents')
                if action == 'mark_processed_selected':
                    res = db.documents.update_many({'_id': {'$in': oids}}, {'$set': {'is_processed': True}})
                    messages.success(request, f'Marked {res.modified_count} documents as processed')
                    return redirect('admin:library_documents')
                if action == 'export_selected':
                    # export selected ids as CSV
                    out = io.StringIO()
                    writer = csv.writer(out)
                    writer.writerow(['id', 'title', 'filename', 'user_id', 'created_at', 'is_processed'])
                    for oid in oids:
                        d = db.documents.find_one({'_id': oid})
                        if not d:
                            continue
                        writer.writerow([
                            str(d.get('_id')),
                            d.get('title', ''),
                            d.get('filename', ''),
                            str(d.get('user_id')) if d.get('user_id') else '',
                            d.get('created_at'),
                            d.get('is_processed', False),
                        ])
                    resp = HttpResponse(out.getvalue(), content_type='text/csv')
                    resp['Content-Disposition'] = 'attachment; filename="library_documents_selected.csv"'
                    return resp

        # Query params: search q, processed filter, page
        q = request.GET.get('q', '').strip()
        processed = request.GET.get('processed', 'all')  # all / yes / no
        tag = request.GET.get('tag', '').strip()
        category = request.GET.get('category', '').strip()
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1
        page_size = 20

        filt = {}
        if q:
            # simple case-insensitive regex search on title or filename
            filt['$or'] = [
                {'title': {'$regex': q, '$options': 'i'}},
                {'filename': {'$regex': q, '$options': 'i'}},
            ]

        if tag:
            filt['tags'] = tag

        if category:
            filt['category'] = category

        if processed == 'yes':
            filt['is_processed'] = True
        elif processed == 'no':
            filt['is_processed'] = False

        total = db.documents.count_documents(filt)
        skip = (page - 1) * page_size
        cursor = db.documents.find(filt).sort('created_at', -1).skip(skip).limit(page_size)

        documents = []
        for d in cursor:
            documents.append({
                'id': str(d.get('_id')),
                'title': d.get('title') or '',
                'filename': d.get('filename') or '',
                'user_id': str(d.get('user_id')) if d.get('user_id') else None,
                'category': d.get('category', ''),
                'tags': d.get('tags', []),
                'created_at': d.get('created_at'),
                'is_processed': d.get('is_processed', False),
                'excerpt': (d.get('content') or '')[:400].replace('\n', ' '),
                'file': d.get('file'),
            })

        # pagination
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        # preserve query params for paging links
        base_qs = {}
        if q:
            base_qs['q'] = q
        if processed and processed != 'all':
            base_qs['processed'] = processed
        if tag:
            base_qs['tag'] = tag
        if category:
            base_qs['category'] = category

        context = dict(
            self.admin_site.each_context(request),
            title='Library documents',
            documents=documents,
            q=q,
            processed=processed,
            page=page,
            total=total,
            total_pages=total_pages,
            page_size=page_size,
            base_qs=urlencode(base_qs),
        )
        return TemplateResponse(request, 'admin/library/documents_list.html', context)

    def documents_export(self, request):
        # export current filter as CSV
        if not getattr(request.user, 'is_staff', False):
            raise PermissionDenied()

        db = get_db()
        q = request.GET.get('q', '').strip()
        processed = request.GET.get('processed', 'all')
        doc_id = request.GET.get('id')

        filt = {}
        if doc_id:
            # export a single document by id
            try:
                oid = ObjectId(doc_id)
                cursor = [db.documents.find_one({'_id': oid})]
            except Exception:
                cursor = []
        else:
            if q:
                filt['$or'] = [
                    {'title': {'$regex': q, '$options': 'i'}},
                    {'filename': {'$regex': q, '$options': 'i'}},
                ]
            if processed == 'yes':
                filt['is_processed'] = True
            elif processed == 'no':
                filt['is_processed'] = False

            cursor = db.documents.find(filt).sort('created_at', -1)

        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(['id', 'title', 'filename', 'user_id', 'created_at', 'is_processed'])
        for d in cursor:
            if not d:
                continue
            writer.writerow([
                str(d.get('_id')),
                d.get('title', ''),
                d.get('filename', ''),
                str(d.get('user_id')) if d.get('user_id') else '',
                d.get('created_at'),
                d.get('is_processed', False),
            ])

        resp = HttpResponse(out.getvalue(), content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="library_documents_export.csv"'
        return resp

    def document_create(self, request):
        if not getattr(request.user, 'is_staff', False):
            raise PermissionDenied()
        db = get_db()

        if request.method == 'POST':
            title = request.POST.get('title', '').strip()
            filename = request.POST.get('filename', '').strip()
            content = request.POST.get('content', '').strip()
            metadata_raw = request.POST.get('metadata', '').strip()
            metadata = {}
            if metadata_raw:
                try:
                    metadata = json.loads(metadata_raw)
                except Exception:
                    metadata = {'raw': metadata_raw}
            # handle file upload
            file_info = None
            uploaded = request.FILES.get('file')
            if uploaded:
                orig_name = os.path.basename(uploaded.name)
                ext = os.path.splitext(orig_name)[1]
                dest_name = f"library/{uuid4().hex}{ext}"
                saved_path = default_storage.save(dest_name, uploaded)
                file_url = default_storage.url(saved_path)
                file_info = {
                    'path': saved_path,
                    'name': orig_name,
                    'size': uploaded.size,
                    'mime': mimetypes.guess_type(orig_name)[0] or '',
                    'url': file_url,
                }
                # attempt OCR/extract text for PDFs if PyMuPDF available
                try:
                    file_fs_path = None
                    try:
                        file_fs_path = default_storage.path(saved_path)
                    except Exception:
                        file_fs_path = None
                    if fitz and file_fs_path and orig_name.lower().endswith('.pdf'):
                        try:
                            pdf_doc = fitz.open(file_fs_path)
                            text = []
                            for p in pdf_doc:
                                text.append(p.get_text())
                            extracted = '\n'.join(text)
                            metadata.setdefault('ocr', {})
                            metadata['ocr']['status'] = 'ok'
                            metadata['ocr']['chars'] = len(extracted)
                            content = extracted
                            excerpt = extracted[:400].replace('\n', ' ')
                        except Exception as e:
                            metadata.setdefault('ocr', {})
                            metadata['ocr']['status'] = 'failed'
                            metadata['ocr']['error'] = str(e)
                except Exception:
                    # keep going if OCR fails
                    pass

            doc = {
                'title': title,
                'filename': filename or (file_info['name'] if file_info else ''),
                'content': content,
                'excerpt': excerpt if 'excerpt' in locals() else ((content or '')[:400].replace('\n', ' ') if content else ''),
                'metadata': metadata,
                'is_processed': False,
            }
            if file_info:
                doc['file'] = file_info
            # tags and category
            tags_raw = request.POST.get('tags', '').strip()
            if tags_raw:
                doc['tags'] = [t.strip() for t in tags_raw.split(',') if t.strip()]
            category = request.POST.get('category', '').strip()
            if category:
                doc['category'] = category
            res = db.documents.insert_one(doc)
            messages.success(request, f'Document created ({res.inserted_id})')
            return redirect('admin:library_document_detail', doc_id=str(res.inserted_id))

        context = dict(self.admin_site.each_context(request), title='Add document')
        return TemplateResponse(request, 'admin/library/document_form.html', context)

    def document_edit(self, request, doc_id: str):
        if not getattr(request.user, 'is_staff', False):
            raise PermissionDenied()
        db = get_db()
        try:
            oid = ObjectId(doc_id)
        except Exception:
            messages.error(request, 'Invalid document id')
            return redirect('admin:library_documents')

        doc = db.documents.find_one({'_id': oid})
        if not doc:
            messages.error(request, 'Document not found')
            return redirect('admin:library_documents')

        if request.method == 'POST':
            title = request.POST.get('title', '').strip()
            filename = request.POST.get('filename', '').strip()
            content = request.POST.get('content', '').strip()
            metadata_raw = request.POST.get('metadata', '').strip()
            metadata = {}
            if metadata_raw:
                try:
                    metadata = json.loads(metadata_raw)
                except Exception:
                    metadata = {'raw': metadata_raw}

            update = {
                'title': title,
                'filename': filename,
                'content': content,
                'metadata': metadata,
            }

            # handle new file upload (replace existing)
            uploaded = request.FILES.get('file')
            if uploaded:
                # remove old file if present
                old = doc.get('file')
                if old and old.get('path') and default_storage.exists(old.get('path')):
                    try:
                        default_storage.delete(old.get('path'))
                    except Exception:
                        pass
                orig_name = os.path.basename(uploaded.name)
                ext = os.path.splitext(orig_name)[1]
                dest_name = f"library/{uuid4().hex}{ext}"
                saved_path = default_storage.save(dest_name, uploaded)
                file_url = default_storage.url(saved_path)
                file_info = {
                    'path': saved_path,
                    'name': orig_name,
                    'size': uploaded.size,
                    'mime': mimetypes.guess_type(orig_name)[0] or '',
                    'url': file_url,
                }
                update['file'] = file_info
                # attempt OCR/extract text for PDFs if PyMuPDF available
                try:
                    file_fs_path = None
                    try:
                        file_fs_path = default_storage.path(saved_path)
                    except Exception:
                        file_fs_path = None
                    if fitz and file_fs_path and orig_name.lower().endswith('.pdf'):
                        try:
                            pdf_doc = fitz.open(file_fs_path)
                            text = []
                            for p in pdf_doc:
                                text.append(p.get_text())
                            extracted = '\n'.join(text)
                            update['content'] = extracted
                            update['excerpt'] = extracted[:400].replace('\n', ' ')
                            metadata = doc.get('metadata', {}) or {}
                            metadata.setdefault('ocr', {})
                            metadata['ocr']['status'] = 'ok'
                            metadata['ocr']['chars'] = len(extracted)
                            update['metadata'] = metadata
                        except Exception as e:
                            metadata = doc.get('metadata', {}) or {}
                            metadata.setdefault('ocr', {})
                            metadata['ocr']['status'] = 'failed'
                            metadata['ocr']['error'] = str(e)
                            update['metadata'] = metadata
                except Exception:
                    pass

            # tags and category
            tags_raw = request.POST.get('tags', '').strip()
            if tags_raw:
                update['tags'] = [t.strip() for t in tags_raw.split(',') if t.strip()]
            category = request.POST.get('category', '').strip()
            if category:
                update['category'] = category

            db.documents.update_one({'_id': oid}, {'$set': update})
            messages.success(request, 'Document updated')
            return redirect('admin:library_document_detail', doc_id=doc_id)

        context = dict(self.admin_site.each_context(request), title=f"Edit: {doc.get('title')}", document={
            'id': str(doc.get('_id')),
            'title': doc.get('title', ''),
            'filename': doc.get('filename', ''),
            'content': doc.get('content', ''),
            'metadata': json.dumps(doc.get('metadata', {}), indent=2),
        })
        return TemplateResponse(request, 'admin/library/document_form.html', context)

    def document_detail(self, request, doc_id: str):
        db = get_db()
        try:
            oid = ObjectId(doc_id)
        except Exception:
            messages.error(request, 'Invalid document id')
            return redirect('admin:library_documents')

        doc = db.documents.find_one({'_id': oid})
        if not doc:
            messages.error(request, 'Document not found')
            return redirect('admin:library_documents')

        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'delete':
                db.documents.delete_one({'_id': oid})
                messages.success(request, 'Document deleted')
                return redirect('admin:library_documents')
            if action == 'mark_processed':
                db.documents.update_one({'_id': oid}, {'$set': {'is_processed': True}})
                messages.success(request, 'Document marked as processed')
                return redirect('admin:library_document_detail', doc_id=doc_id)

        context = dict(
            self.admin_site.each_context(request),
            title=f"Document: {doc.get('title')}",
            document={
                'id': str(doc.get('_id')),
                'title': doc.get('title'),
                'filename': doc.get('filename'),
                'user_id': str(doc.get('user_id')) if doc.get('user_id') else None,
                'created_at': doc.get('created_at'),
                'is_processed': doc.get('is_processed', False),
                'metadata': doc.get('metadata', {}),
                'content': doc.get('content', ''),
            }
        )
        return TemplateResponse(request, 'admin/library/document_detail.html', context)

    # ----------------------- Community posts admin -----------------------
    def posts_list(self, request):
        if not getattr(request.user, 'is_staff', False):
            raise PermissionDenied()
        db = get_db()

        # Handle bulk actions
        if request.method == 'POST':
            action = request.POST.get('action')
            ids = request.POST.getlist('selected_ids')
            if ids:
                oids = []
                for s in ids:
                    try:
                        oids.append(ObjectId(s))
                    except Exception:
                        continue
                if action == 'delete_selected':
                    res = db.community_posts.delete_many({'_id': {'$in': oids}})
                    messages.success(request, f'Deleted {res.deleted_count} posts')
                    return redirect('admin:library_posts')
                if action == 'pin_selected':
                    res = db.community_posts.update_many({'_id': {'$in': oids}}, {'$set': {'is_pinned': True}})
                    messages.success(request, f'Pinned {res.modified_count} posts')
                    return redirect('admin:library_posts')
                if action == 'unpin_selected':
                    res = db.community_posts.update_many({'_id': {'$in': oids}}, {'$set': {'is_pinned': False}})
                    messages.success(request, f'Unpinned {res.modified_count} posts')
                    return redirect('admin:library_posts')

        q = request.GET.get('q', '').strip()
        category = request.GET.get('category', '').strip()
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1
        page_size = 20

        filt = {}
        if category and category != 'all':
            filt['category'] = category
        if q:
            filt['$or'] = [
                {'title': {'$regex': q, '$options': 'i'}},
                {'content': {'$regex': q, '$options': 'i'}}
            ]

        total = db.community_posts.count_documents(filt)
        skip = (page - 1) * page_size
        cursor = db.community_posts.find(filt).sort([('is_pinned', -1), ('updated_at', -1)]).skip(skip).limit(page_size)

        posts = []
        for p in cursor:
            posts.append({
                'id': str(p.get('_id')),
                'title': p.get('title', ''),
                'category': p.get('category', ''),
                'tags': p.get('tags', []),
                'user_id': str(p.get('user_id')) if p.get('user_id') else None,
                'likes': len(p.get('likes', [])),
                'views': p.get('views', 0),
                'created_at': p.get('created_at'),
                'is_pinned': p.get('is_pinned', False),
                'is_solved': p.get('is_solved', False),
            })

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        base_qs = {}
        if q:
            base_qs['q'] = q
        if category:
            base_qs['category'] = category

        context = dict(
            self.admin_site.each_context(request),
            title='Community posts',
            posts=posts,
            q=q,
            category=category,
            page=page,
            total=total,
            total_pages=total_pages,
            page_size=page_size,
            base_qs=urlencode(base_qs),
        )
        return TemplateResponse(request, 'admin/library/posts_list.html', context)

    def post_detail(self, request, post_id: str):
        if not getattr(request.user, 'is_staff', False):
            raise PermissionDenied()
        db = get_db()
        try:
            oid = ObjectId(post_id)
        except Exception:
            messages.error(request, 'Invalid post id')
            return redirect('admin:library_posts')

        post = db.community_posts.find_one({'_id': oid})
        if not post:
            messages.error(request, 'Post not found')
            return redirect('admin:library_posts')

        # actions: delete, toggle pin, toggle solved, delete comment
        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'delete':
                db.community_posts.delete_one({'_id': oid})
                messages.success(request, 'Post deleted')
                return redirect('admin:library_posts')
            if action == 'toggle_pin':
                db.community_posts.update_one({'_id': oid}, {'$set': {'is_pinned': not post.get('is_pinned', False)}})
                messages.success(request, 'Pin toggled')
                return redirect('admin:library_post_detail', post_id=post_id)
            if action == 'toggle_solved':
                db.community_posts.update_one({'_id': oid}, {'$set': {'is_solved': not post.get('is_solved', False)}})
                messages.success(request, 'Solved toggled')
                return redirect('admin:library_post_detail', post_id=post_id)
            if action == 'delete_comment':
                # expect comment_index in POST
                try:
                    idx = int(request.POST.get('comment_index'))
                    # pull by position is not atomic in mongodb easily; we'll read, remove and update
                    post = db.community_posts.find_one({'_id': oid})
                    comments = post.get('comments', [])
                    if 0 <= idx < len(comments):
                        comments.pop(idx)
                        db.community_posts.update_one({'_id': oid}, {'$set': {'comments': comments}})
                        messages.success(request, 'Comment deleted')
                except Exception:
                    messages.error(request, 'Invalid comment index')
                return redirect('admin:library_post_detail', post_id=post_id)

        context = dict(
            self.admin_site.each_context(request),
            title=f"Post: {post.get('title')}",
            post=post,
        )
        return TemplateResponse(request, 'admin/library/post_detail.html', context)

    def post_create(self, request):
        if not getattr(request.user, 'is_staff', False):
            raise PermissionDenied()
        db = get_db()
        if request.method == 'POST':
            title = request.POST.get('title', '').strip()
            content = request.POST.get('content', '').strip()
            category = request.POST.get('category', '').strip() or 'general'
            tags_raw = request.POST.get('tags', '').strip()
            tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
            now = __import__('datetime').datetime.utcnow()
            post = {
                'title': title,
                'content': content,
                'category': category,
                'tags': tags,
                'likes': [],
                'comments': [],
                'views': 0,
                'is_pinned': False,
                'is_solved': False,
                'created_at': now,
                'updated_at': now,
            }
            res = db.community_posts.insert_one(post)
            messages.success(request, 'Post created')
            return redirect('admin:library_post_detail', post_id=str(res.inserted_id))

        context = dict(self.admin_site.each_context(request), title='Add post')
        return TemplateResponse(request, 'admin/library/post_form.html', context)

    def post_edit(self, request, post_id: str):
        if not getattr(request.user, 'is_staff', False):
            raise PermissionDenied()
        db = get_db()
        try:
            oid = ObjectId(post_id)
        except Exception:
            messages.error(request, 'Invalid post id')
            return redirect('admin:library_posts')
        post = db.community_posts.find_one({'_id': oid})
        if not post:
            messages.error(request, 'Post not found')
            return redirect('admin:library_posts')

        if request.method == 'POST':
            title = request.POST.get('title', '').strip()
            content = request.POST.get('content', '').strip()
            category = request.POST.get('category', '').strip() or 'general'
            tags_raw = request.POST.get('tags', '').strip()
            tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
            update = {
                'title': title,
                'content': content,
                'category': category,
                'tags': tags,
                'updated_at': __import__('datetime').datetime.utcnow(),
            }
            db.community_posts.update_one({'_id': oid}, {'$set': update})
            messages.success(request, 'Post updated')
            return redirect('admin:library_post_detail', post_id=post_id)

        context = dict(self.admin_site.each_context(request), title=f"Edit: {post.get('title')}", post=post)
        return TemplateResponse(request, 'admin/library/post_form.html', context)


# Hook into the default admin site by extending its urls
library_views = LibraryAdminViews()
library_views.admin_site = admin.site

# insert urls into admin
admin.site.get_urls = (lambda orig_get_urls=admin.site.get_urls: (lambda: library_views.get_urls() + orig_get_urls()))()
