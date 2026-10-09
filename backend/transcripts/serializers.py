# transcripts/serializers.py
from rest_framework import serializers
from .models import Transcript, TranscriptPage


class TranscriptUploadSerializer(serializers.ModelSerializer):
    files = serializers.ListField(
        child=serializers.FileField(),
        allow_empty=False,
        write_only=True
    )

    def validate_files(self, files):
        from io import BytesIO
        from pathlib import Path
        import pymupdf
        from PIL import Image
        if not 1 <= len(files) <= 5:
            raise serializers.ValidationError('Upload between 1 and 5 files.')
        if sum(file.size for file in files) > 5 * 1024 * 1024:
            raise serializers.ValidationError('Combined upload limit is 5 MiB.')
        for file in files:
            data = file.read()
            file.seek(0)
            extension = Path(file.name).suffix.lower()
            try:
                if extension == '.pdf' and data.startswith(b'%PDF-'):
                    with pymupdf.open(stream=data, filetype='pdf') as pdf:
                        if pdf.needs_pass or not 1 <= len(pdf) <= 50:
                            raise ValueError('Invalid or encrypted PDF')
                        for page in pdf:
                            if page.rect.width <= 0 or page.rect.height <= 0 or page.rect.width * page.rect.height * (200 / 72) ** 2 > 20_000_000:
                                raise ValueError('Page too large')
                            page.get_text()
                elif (extension == '.png' and data.startswith(b'\x89PNG\r\n\x1a\n')) or (
                    extension in ('.jpg', '.jpeg') and data.startswith(b'\xff\xd8\xff')):
                    with Image.open(BytesIO(data)) as image:
                        if image.width * image.height > 20_000_000 or getattr(image, 'n_frames', 1) != 1:
                            raise ValueError('Image too large or animated')
                        if image.format not in ('JPEG', 'PNG'):
                            raise ValueError('Invalid image format')
                        image.verify()
                    with Image.open(BytesIO(data)) as image:
                        image.load()
                else:
                    raise ValueError('Unsupported signature')
            except Exception as exc:
                raise serializers.ValidationError('Upload a decodable, unencrypted PDF, JPG, or PNG (up to 50 PDF pages / 20 megapixels per page).') from exc
        return files

    def create(self, validated_data):
        user = self.context['request'].user
        # validated_data에서 'files'를 분리
        files = validated_data.pop('files')

        # Transcript 레코드 생성 (user만으로)
        transcript = Transcript.objects.create(user=user, **validated_data)

        # 페이지별 파일 저장
        for idx, f in enumerate(files, start=1):
            TranscriptPage.objects.create(
                transcript=transcript,
                file=f,
                page_number=idx
            )
        return transcript

    class Meta:
        model = Transcript
        # 이제 이 필드들이 정상적으로 응답에 포함됩니다.
        fields = ['id', 'files', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']


class TranscriptStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transcript
        fields = ['id', 'status', 'error_message']


class TranscriptParsedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transcript
        fields = ['id', 'parsed_data']
