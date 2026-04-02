'use client';

import React, { useCallback, useState } from 'react';
import { Upload, X, FileText, Image, FileSpreadsheet, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { DOCUMENT_TYPES } from '@/lib/constants';

export interface FileItem {
  file: File;
  id: string;
  documentType: string;
  preview?: string;
}

interface FileDropZoneProps {
  files: FileItem[];
  onFilesChange: (files: FileItem[]) => void;
  maxFiles?: number;
  maxSizeMB?: number;
}

function getFileIcon(file: File) {
  if (file.type === 'application/pdf') return <FileText className="w-5 h-5 text-red-400" />;
  // eslint-disable-next-line jsx-a11y/alt-text
  if (file.type.startsWith('image/')) return <Image className="w-5 h-5 text-blue-400" aria-hidden="true" />;
  if (file.type.includes('csv') || file.name.endsWith('.csv')) return <FileSpreadsheet className="w-5 h-5 text-green-400" />;
  return <FileText className="w-5 h-5 text-t-muted" />;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileDropZone({
  files,
  onFilesChange,
  maxFiles = 6,
  maxSizeMB = 20,
}: FileDropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addFiles = useCallback(
    (newFiles: File[]) => {
      setError(null);
      const valid: FileItem[] = [];
      const acceptedTypes = [
        'application/pdf',
        'image/png',
        'image/jpeg',
        'image/jpg',
        'text/csv',
        'application/vnd.ms-excel',
      ];

      for (const file of newFiles) {
        if (files.length + valid.length >= maxFiles) {
          setError(`Maximum ${maxFiles} files allowed.`);
          break;
        }
        if (file.size > maxSizeMB * 1024 * 1024) {
          setError(`${file.name} exceeds the ${maxSizeMB}MB size limit.`);
          continue;
        }
        const isAccepted =
          acceptedTypes.includes(file.type) ||
          file.name.endsWith('.csv') ||
          file.name.endsWith('.pdf');
        if (!isAccepted) {
          setError(`${file.name} is not a supported format. Use PDF, PNG, JPG, or CSV.`);
          continue;
        }
        valid.push({
          file,
          id: `${file.name}-${Date.now()}-${Math.random()}`,
          documentType: '',
        });
      }
      if (valid.length > 0) onFilesChange([...files, ...valid]);
    },
    [files, maxFiles, maxSizeMB, onFilesChange]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      addFiles(Array.from(e.dataTransfer.files));
    },
    [addFiles]
  );

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) addFiles(Array.from(e.target.files));
      e.target.value = '';
    },
    [addFiles]
  );

  const removeFile = useCallback(
    (id: string) => onFilesChange(files.filter((f) => f.id !== id)),
    [files, onFilesChange]
  );

  const updateDocumentType = useCallback(
    (id: string, type: string) => {
      onFilesChange(files.map((f) => (f.id === id ? { ...f, documentType: type } : f)));
    },
    [files, onFilesChange]
  );

  return (
    <div className="space-y-4">
      <div
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        className={cn(
          'relative border-2 border-dashed rounded-2xl p-10 text-center transition-all duration-200 cursor-pointer',
          isDragOver
            ? 'border-accent bg-accent/5 shadow-lg shadow-accent/10'
            : 'border-white/[0.1] bg-surface hover:border-accent/30 hover:bg-surface'
        )}
        onClick={() => document.getElementById('file-input')?.click()}
      >
        <input
          id="file-input"
          type="file"
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.csv"
          className="hidden"
          onChange={onInputChange}
        />
        <Upload className={cn('w-10 h-10 mx-auto mb-3 transition-colors', isDragOver ? 'text-accent' : 'text-t-muted')} />
        <p className="text-base font-semibold text-white mb-1">
          {isDragOver ? 'Drop files here' : 'Drag & drop your documents'}
        </p>
        <p className="text-sm text-t-secondary mb-4">or click to browse</p>
        <div className="flex items-center justify-center gap-2">
          {['PDF', 'PNG', 'JPG', 'CSV'].map((fmt) => (
            <span
              key={fmt}
              className="px-2.5 py-1 bg-raised text-t-secondary rounded text-xs font-medium border border-white/[0.06]"
            >
              {fmt}
            </span>
          ))}
        </div>
        <p className="text-xs text-t-muted mt-3">Max {maxFiles} files · {maxSizeMB}MB per file</p>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-risk-critical text-sm bg-risk-critical/10 border border-risk-critical/20 rounded-lg px-4 py-3">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {files.length > 0 && (
        <div className="space-y-3">
          {files.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-3 p-4 bg-surface border border-white/[0.06] rounded-xl"
            >
              <div className="flex-shrink-0">{getFileIcon(item.file)}</div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">{item.file.name}</p>
                <p className="text-xs text-t-muted">{formatFileSize(item.file.size)}</p>
              </div>
              <div className="flex-shrink-0 w-52">
                <Select
                  value={item.documentType}
                  onValueChange={(v) => updateDocumentType(item.id, v ?? '')}
                >
                  <SelectTrigger className="h-8 text-xs bg-raised border-white/[0.08]">
                    <SelectValue placeholder="Select document type..." />
                  </SelectTrigger>
                  <SelectContent>
                    {DOCUMENT_TYPES.map((dt) => (
                      <SelectItem key={dt.value} value={dt.value} className="text-xs">
                        {dt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); removeFile(item.id); }}
                className="flex-shrink-0 p-1.5 text-t-muted hover:text-risk-critical hover:bg-risk-critical/10 rounded-lg transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
